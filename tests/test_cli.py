from material_colors_grid.cli import main


def test_version_flag_returns_success() -> None:
    assert main(["--version"]) == 0


def test_unimplemented_cli_fails_gracefully() -> None:
    assert main([]) == 1
