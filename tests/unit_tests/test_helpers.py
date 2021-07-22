from face_rhythm.util import helpers, setup

from pathlib import Path
import shutil



def run_basic(run_name):
    project_path = Path('test_runs').resolve() / run_name
    video_path = Path('test_data').resolve() / run_name / 'session1'
    overwrite_config = True
    remote = True
    trials = False
    multisession = False

    config_filepath = setup.setup_project(project_path, video_path, run_name, overwrite_config, remote, trials,
                                          multisession)
    return config_filepath

def test_config_roundtrip():
    run_name = 'single_session_single_video'
    config_filepath = run_basic(run_name)
    config = helpers.load_config(config_filepath)
    helpers.save_config(config, config_filepath)
    new_config = helpers.load_config(config_filepath)
    assert config == new_config
