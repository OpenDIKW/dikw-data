# Dataset Format

`dikw-data` stores versioned evaluation datasets under `datasets/<dataset>/`.
Each dataset is self-contained and should be readable without consulting
`generated/`.

## Text Dataset Layout

```text
datasets/<dataset>/
  dataset.yaml
  queries.yaml
  corpus/
    *.md
```

### `dataset.yaml`

```yaml
name: synthetic-diverse-v2
description: >
  Human-readable dataset description.
thresholds:
  hit_at_3: 0.85
  hit_at_10: 0.90
  mrr: 0.75
```

Fields:

- `name`: stable dataset identifier. It should match the directory name.
- `description`: short purpose and coverage description.
- `thresholds`: optional doc-level metric thresholds for current `dikw-core`
  compatibility evaluation.

### `corpus/*.md`

Each Markdown file is one retrievable document for the current doc-level
runner. Synthetic corpus files should be factual, compact, and internally
consistent. Prefer stable headings and explicit facts that can be targeted by
queries.

### `queries.yaml`

Text datasets use query records like:

```yaml
- id: zh_qin_unification_001
  q: 秦统一六国后推行了哪些制度来加强中央集权？
  expect_any: [chinese-history-qin-unification]
```

Fields:

- `id`: stable query identifier.
- `q`: natural-language retrieval query.
- `expect_any`: accepted document IDs for doc-level hit metrics.

## Multimodal Dataset Layout

`synthetic-multimodal-datasets-v1` extends the base shape with local image
assets and target metadata:

```text
datasets/synthetic-multimodal-datasets-v1/
  dataset.yaml
  targets.yaml
  queries.yaml
  corpus/
    fruits.md
    animals.md
    ...
    images/
      fruits/*.png
      animals/*.png
      ...
```

Each category has one Markdown file. Each object has:

- one `##` section,
- one stable target marker, such as `Target: fruits.apple`,
- one local image reference,
- one asset target,
- one text chunk target,
- one asset query,
- one text chunk query.

### Markdown Section Example

```markdown
## 苹果 / Apple

Target: fruits.apple

![苹果 / Apple](images/fruits/apple.png)

苹果通常呈圆形或近圆形，外皮可为红色、绿色或黄色。
```

### `targets.yaml`

```yaml
assets:
  - id: fruits.apple.image
    doc: fruits
    path: images/fruits/apple.png
    heading: 苹果 / Apple

chunks:
  - id: fruits.apple.text
    doc: fruits
    heading: 苹果 / Apple
    anchor: fruits.apple
    asset_id: fruits.apple.image
```

Fields:

- `assets[].id`: stable image target ID.
- `assets[].doc`: Markdown document stem under `corpus/`.
- `assets[].path`: image path relative to `corpus/`.
- `assets[].heading`: section heading containing the image.
- `chunks[].id`: stable text-section target ID.
- `chunks[].anchor`: stable marker inside the Markdown section.
- `chunks[].asset_id`: related image asset target.

### Multimodal `queries.yaml`

```yaml
- id: fruits_apple_asset_zh
  query_type: asset
  q: 哪张图片展示了红色圆形苹果和绿色叶片？
  expect_any: [fruits]
  expect_asset_any: [fruits.apple.image]

- id: fruits_apple_chunk_zh
  query_type: text_chunk
  q: 苹果的小节介绍了哪些视觉特征？
  expect_any: [fruits]
  expect_chunk_any: [fruits.apple.text]
```

Fields:

- `query_type`: `asset` or `text_chunk`.
- `expect_any`: doc-level compatibility target for current `dikw-core`.
- `expect_asset_any`: accepted image asset IDs.
- `expect_chunk_any`: accepted text chunk IDs.

## Validation

Run:

```powershell
uv run python scripts/validate_dataset.py datasets/<dataset>
```

The validator checks:

- required files exist,
- corpus Markdown files exist,
- supported threshold names are used,
- query `expect_any` targets resolve to corpus documents,
- multimodal `targets.yaml` references resolve,
- image files exist,
- Markdown image references point to existing local files,
- asset/chunk query targets resolve.
