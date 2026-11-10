from material_colors_grid import Category, Color, Err, Ok, ProjectDocument, Result


def check(result: Result[int]) -> str:
    if isinstance(result, Err):
        return result.error
    return str(result.value)


def test_ok_and_err_are_distinguishable() -> None:
    assert check(Ok(3)) == "3"
    assert check(Err("bad hex")) == "bad hex"


def test_default_document_matches_typescript_defaults() -> None:
    document: ProjectDocument = ProjectDocument()
    assert (document.style.width, document.style.height) == (1440, 1280)
    assert document.categories == ()


def test_category_nests_colors_and_sub_categories() -> None:
    color: Color = Color(id="c1", name="Matte Black", hex="#111111")
    inner: Category = Category(id="s1", name="Matte", colors=(color,))
    outer: Category = Category(id="p1", name="PLA", sub_categories=(inner,))
    assert outer.sub_categories[0].colors[0].name == "Matte Black"
