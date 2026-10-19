# Staging: annotation, layer 1

*DRAFT, not yet reviewed (2026-10-17).* Each file here is written exactly as it will be in its final
place, final imports included, so moving it in is a plain move. Nothing in `src/` imports from this
folder (its name has a hyphen, so it cannot be imported as a package).

| file here | goes to | what it is |
| --- | --- | --- |
| `models_additions.py` | appended to `src/models.py` | `End`, `TargetDescription`, `AnnotationDescription`: annotations as written, what every annotation format produces (as `UnitDescription` is for representations) |
| `annotations/__init__.py` | `src/annotations/__init__.py` | empty: makes `annotations` a package, as `representations/` is |
| `annotations/notes_text.py` | `src/annotations/notes_text.py` | the notes text format: `parse` turns a `.notes.txt` file into `AnnotationDescription`s (as `representations/tei_display.py` reads a source) |
| `annotation.py` | `src/annotation.py` | `resolve`: `AnnotationDescription`s against a version → `Annotation`s; independent of any format (as `matching.py` places what representations describe) |
| `works.py` | `src/works.py` | the corpus layout: `work_of` finds a file's work, `compose_version` composes a version of it by name |
| `synthesis_additions.py` | into `src/synthesis.py` | the `--notes FILE` option: the imports marked NEW, `NOTES_SUFFIX`, `read_notes`, `show_annotations`, `describe_target`, and `main` with its CHANGED lines |
| `try_notes.py` | — (delete with this folder) | runs the staged `--notes` option before anything is moved |

Try it, from `loom/`:

```powershell
python src/test-annotations/try_notes.py --notes text/shakespeare/sonnet-116/annotations/<file>.notes.txt
```

Review order: `models_additions.py`, `annotations/notes_text.py`, `annotation.py`, `works.py`,
`synthesis_additions.py`.
