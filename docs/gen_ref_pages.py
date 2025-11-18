"""Generate API reference pages automatically."""

from pathlib import Path

import mkdocs_gen_files

nav = mkdocs_gen_files.Nav()

# Scan the dossier package
for path in sorted(Path("dossier").rglob("*.py")):
    module_path = path.relative_to(".").with_suffix("")
    doc_path = path.relative_to("dossier").with_suffix(".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    # Skip __pycache__ and private modules
    if "__pycache__" in parts or any(part.startswith("_") for part in parts[1:]):
        continue

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"# `{ident}`\n\n")
        fd.write(f"::: {ident}\n")
        fd.write("    options:\n")
        fd.write("      members: true\n")
        fd.write("      inherited_members: true\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

# Create reference index page
with mkdocs_gen_files.open("reference/index.md", "w") as index_file:
    index_file.write("# API Reference\n\n")
    index_file.write("Auto-generated documentation from source code.\n\n")
    index_file.writelines(nav.build_literate_nav())

# Also write SUMMARY for literate-nav
with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
