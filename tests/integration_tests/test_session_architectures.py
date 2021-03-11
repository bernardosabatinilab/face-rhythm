import cv2
import numpy as np
import h5py

from face_rhythm.util import helpers, set_roi, setup
from face_rhythm.optic_flow import optic_flow, clean_results, conv_dim_reduce
from face_rhythm.analysis import pca, spectral_analysis, tca

from pathlib import Path


def test_single_session_single_video():
    # SETUP
    run_name = 'single_session_single_video'
    project_path = Path('test_runs/'+run_name).resolve()
    video_path = Path('test_data/'+run_name).resolve()
    overwrite_config = False
    remote = False
    trials = False

    config_filepath = setup.setup_project(project_path, video_path, run_name, overwrite_config, remote, trials)

    # VIDEO LOAD
    config = helpers.load_config(config_filepath)
    config['Video']['session_prefix'] = 'session'
    config['Video']['print_filenames'] = True
    config['General']['overwrite_nwbs'] = False
    helpers.save_config(config, config_filepath)

    setup.prepare_videos(config_filepath)

    # ROI Selection
    config = helpers.load_config(config_filepath)
    config['ROI']['session_to_set'] = 0  # 0 indexed. Chooses the session to use
    config['ROI']['vid_to_set'] = 0  # 0 indexed. Sets the video to use to make an image
    config['ROI']['frame_to_set'] = 1  # 0 indexed. Sets the frame number to use to make an image
    config['ROI']['load_from_file'] = True  # if you've already run this and want to use the existing ROI, set to True
    helpers.save_config(config, config_filepath)
    #special line to just grab the points
    with h5py.File(Path('test_data/pts_all.h5'), 'r') as pt:
        pts_all = helpers.h5_to_dict(pt)
    helpers.save_h5(config_filepath, 'pts_all', pts_all)

    # Optic Flow
    config = helpers.load_config(config_filepath)
    config['Optic']['vidNums_toUse'] = [0]
    config['Optic']['spacing'] = 16
    config['Optic']['showVideo_pref'] = False
    config['Video']['printFPS_pref'] = False
    config['Video']['fps_counterPeriod'] = 10
    config['Video']['dot_size'] = 1
    config['Video']['save_demo'] = False
    config['Video']['demo_len'] = 10
    config['Optic']['lk'] = {}
    config['Optic']['lk']['winSize'] = (15, 15)
    config['Optic']['lk']['maxLevel'] = 2
    config['Optic']['lk']['criteria'] = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 3, 0.001)
    config['Optic']['recursive'] = False
    config['Optic']['recursive_relaxation_factor'] = 0.005
    config['Optic']['multithread'] = False
    helpers.save_config(config, config_filepath)

    optic_flow.optic_workflow(config_filepath)

    # Clean Up
    config = helpers.load_config(config_filepath)
    config['Clean']['outlier_threshold_positions'] = 25
    config['Clean']['outlier_threshold_displacements'] = 4
    config['Clean']['framesHalted_beforeOutlier'] = 4
    config['Clean']['framesHalted_afterOutlier'] = 2
    config['Clean']['relaxation_factor'] = 0.005
    helpers.save_config(config, config_filepath)

    clean_results.clean_workflow(config_filepath)

    # ConvDR
    config = helpers.load_config(config_filepath)
    pointInds_toUse = helpers.load_data(config_filepath, 'pointInds_toUse')
    config['CDR']['width_cosKernel'] = 48
    config['CDR']['num_dots'] = pointInds_toUse.shape[0]
    config['CDR']['spacing'] = 16
    config['CDR']['display_points'] = False
    config['CDR']['vidNum'] = 0
    config['CDR']['frameNum'] = 1
    config['CDR']['dot_size'] = 1
    config['CDR']['kernel_alpha'] = 0.3
    config['CDR']['kernel_pixel'] = 10
    config['CDR']['num_components'] = 3
    helpers.save_config(config, config_filepath)

    conv_dim_reduce.conv_dim_reduce_workflow(config_filepath)

    pca.pca_workflow(config_filepath, 'positions_convDR_absolute')

    # Positional TCA
    config = helpers.load_config(config_filepath)
    config['TCA']['pref_useGPU'] = False
    config['TCA']['device'] = 'cpu'
    config['TCA']['rank'] = 4
    config['TCA']['init'] = 'random'
    config['TCA']['tolerance'] = 1e-06  # best to set around 1e-05 to 1e-07
    config['TCA']['verbosity'] = 0
    config['TCA']['n_iters'] = 100
    config['TCA']['pref_concat_cartesian_dim'] = True  # New option
    helpers.save_config(config, config_filepath)

    tca.positional_tca_workflow(config_filepath, 'positions_convDR_meanSub')

    #CQT
    config = helpers.load_config(config_filepath)
    eps = 1.19209e-07  # float32 epsilon
    hop_length = 16
    fmin_rough = 1.8
    Fs = config['Video']['Fs']
    sr = Fs
    n_bins = 35
    bins_per_octave = int(np.round((n_bins) / np.log2((Fs / 2) / fmin_rough)))
    fmin = ((Fs / 2) / (2 ** ((n_bins) / bins_per_octave))) - (2 * eps)
    fmax = fmin * (2 ** ((n_bins) / bins_per_octave))
    freqs_Sxx = fmin * (2 ** ((np.arange(n_bins) + 1) / bins_per_octave))

    config = helpers.load_config(config_filepath)
    config['CQT']['hop_length'] = hop_length
    config['CQT']['sr'] = sr
    config['CQT']['n_bins'] = n_bins
    config['CQT']['bins_per_octave'] = bins_per_octave
    config['CQT']['fmin'] = fmin
    config['CQT']['fmin_rough'] = fmin_rough
    config['CQT']['fmax'] = fmax
    config['CQT']['pixelNum_toUse'] = 1
    helpers.save_config(config, config_filepath)
    helpers.save_data(config_filepath, 'freqs_Sxx', freqs_Sxx)

    spectral_analysis.cqt_workflow(config_filepath, 'positions_convDR_meanSub')

    # Spectral TCA
    config = helpers.load_config(config_filepath)
    config['TCA']['pref_useGPU'] = True
    config['TCA']['device'] = 'cpu'
    config['TCA']['rank'] = 8
    config['TCA']['init'] = 'random'  # If the input is small, set init='svd'
    config['TCA']['tolerance'] = 1e-06  # best to set around 1e-05 to 1e-07
    config['TCA']['verbosity'] = 1
    config['TCA']['n_iters'] = 100  # best to set around 100-600
    config['TCA']['pref_concat_cartesian_dim'] = True  # New option
    helpers.save_config(config, config_filepath)

