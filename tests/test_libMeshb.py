import numpy as np

import pyLibMeshb.libMeshb as lm


def test_list_types_without_a_file_returns_registered_types():
    types = lm.list_types()

    assert types == sorted(lm.TYPES)
    assert "vertices" in types
    assert "sol_at_vertices" in types


def test_field_width_depends_on_dimension():
    assert lm._field_width(lm.GmfSca, 2) == 1
    assert lm._field_width(lm.GmfVec, 3) == 3
    assert lm._field_width(lm.GmfSymMat, 2) == 3
    assert lm._field_width(lm.GmfMat, 3) == 9


def test_mesh_and_solution_round_trip(tmp_path):
    mesh_path = tmp_path / "mesh.meshb"
    solution_path = tmp_path / "solution.solb"
    vertices = np.array(
        [
            [0.0, 0.0, 10],
            [1.0, 0.0, 20],
            [0.0, 1.0, 30],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[1, 2, 3, 7]], dtype=np.int64)
    values = np.array([[1.5, 2.5], [3.5, 4.5], [5.5, 6.5]])

    lm.write(
        str(mesh_path),
        {"version": 3, "dim": 2, "vertices": vertices, "triangles": triangles},
    )
    lm.write(
        str(solution_path),
        {"version": 3, "dim": 2, "sol_at_vertices": {"values": values, "field_types": [lm.GmfSca] * 2}},
    )

    assert lm.list_types(str(mesh_path)) == ["triangles", "vertices"]
    assert lm.list_types(str(solution_path)) == ["sol_at_vertices"]

    mesh = lm.read(str(mesh_path), types=["vertices", "triangles"])
    solution = lm.read(str(solution_path), types=["sol_at_vertices"])

    assert mesh["version"] == 3
    assert mesh["dim"] == 2
    np.testing.assert_allclose(mesh["vertices"], vertices)
    np.testing.assert_array_equal(mesh["triangles"], triangles)
    np.testing.assert_allclose(solution["sol_at_vertices"]["values"], values)
    assert solution["sol_at_vertices"]["field_types"] == [lm.GmfSca, lm.GmfSca]


def test_write_uses_version_and_dim_from_data_metadata(tmp_path):
    path = tmp_path / "mesh.meshb"
    vertices = np.array(
        [
            [0.0, 0.0, 0.0, 10],
            [1.0, 0.0, 0.0, 20],
            [0.0, 1.0, 0.0, 30],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[0, 1, 2, 7]], dtype=np.int64)

    lm.write(str(path), {"version": 4, "dim": 3, "vertices": vertices, "triangles": triangles})

    assert lm.mesh_info(str(path)) == (4, 3)
    mesh = lm.read(str(path), types=["vertices", "triangles"])
    assert mesh["version"] == 4
    assert mesh["dim"] == 3
    np.testing.assert_allclose(mesh["vertices"], vertices)


def test_write_infers_dim_from_vertices_when_dim_missing(tmp_path):
    path = tmp_path / "mesh.meshb"
    vertices = np.array(
        [
            [0.0, 0.0, 10],
            [1.0, 0.0, 20],
            [0.0, 1.0, 30],
        ],
        dtype=np.float64,
    )
    triangles = np.array([[0, 1, 2, 7]], dtype=np.int64)

    lm.write(str(path), {"version": 3, "vertices": vertices, "triangles": triangles})

    assert lm.mesh_info(str(path)) == (3, 2)
    mesh = lm.read(str(path), types=["vertices", "triangles"])
    assert mesh["dim"] == 2
    np.testing.assert_allclose(mesh["vertices"], vertices)


def test_mesh_info_reports_file_metadata(tmp_path, capsys):
    path = tmp_path / "mesh.meshb"
    lm.write(
        str(path),
        {"version": 3, "dim": 2, "vertices": np.array([[0.0, 0.0, 1], [1.0, 0.0, 1], [0.0, 1.0, 1]])},
    )

    assert lm.mesh_info(str(path)) == (3, 2)
    output = capsys.readouterr().out
    assert f"File          : {path}" in output
    assert "vertices" in output
