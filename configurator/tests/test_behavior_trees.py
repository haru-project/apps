from pathlib import Path


def test_gaze_enable_check_precedes_tracking_refresh() -> None:
    root = Path(__file__).resolve().parents[2]
    xml = (root / "config" / "behavior_trees" / "simple_gaze_controller.xml").read_text()
    tree = xml.split('<BehaviorTree ID="GazeControllerSimple">', 1)[1]
    enabled = tree.index('<Condition ID="CheckBool" input="$${GazeControllerOn}"/>')
    refresh = tree.index('<Sequence name="Update Tracking">')
    assert enabled < refresh
