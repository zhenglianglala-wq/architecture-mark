---
name: visual-highrise-annotation
description: Create and iteratively refine high-rise building candidate labels from overhead RGB imagery using visual roof-and-shadow evidence, with QGIS-ready review outputs. Use for high-rise annotation previews or candidate layers; do not use it to claim measured building heights.
---

# Visual High-Rise Annotation

Use this skill when the goal is to find **high-rise building candidates** in overhead RGB imagery, then iteratively improve them with user feedback. The desired boundary is the visible outer edge of the physical building entity (roof plus any visually separable building body/facade), never a cast shadow.

## Evidence and decision rule

Read [the visual criteria](references/visual-criteria.md) before annotating a new area.

Create a candidate only when a distinct physical building entity is visible and visual evidence supports a tall structure. Strong, continuous cast shadow is a high-value cue, especially when it is conspicuously longer/darker than shadows of nearby buildings. Confirm it with at least one additional cue: a compact tower-like building form; a visible facade/roof–shadow separation; a height pattern consistent with nearby towers; or a user-provided correction. Trace the building itself, not the adjacent dark projected area.

Do not call a candidate high-rise from roof area, brightness, road adjacency, or a single vague dark patch alone. Exclude bridges, road shadows, canals, trees, construction, long low-rise strips, and ambiguous roof groups.

## Iteration workflow

1. Inspect the original full image before marking. Keep the full image extent; do not restrict to a community boundary unless the user requests it. During a **human iterative-review run**, provide a clickable link to the unannotated source GeoTIFF before the candidate preview so the user can compare other time periods. Do not render or link every original image during an approved batch run unless requested.
2. Produce a visual preview with thin yellow outlines around high-confidence candidates. Preserve source imagery exactly; use no filled masks. During human review, publish it as a generated image so the user can open the Canvas and add marks/comments directly. State that it is a visual candidate preview, not georeferenced truth.
3. Treat colour-marked user feedback as local ground feedback: **red** circles/arrows mean “add this omitted high-rise building”; **green** circles/arrows mean “remove this false positive”; **blue** circles/arrows mean “keep the building but contract its boundary to exclude the marked non-building area”, such as a cast shadow or paved courtyard. Replace correction marks with separate yellow outlines around the physical building boundary where buildings are visually separable. Never use the circle itself or its shadow as a label boundary.
4. Before showing a candidate preview, perform a second, independent quality-control pass: first scan the whole original image for omissions and false positives, then scan overlapping 3×3 or 4×4 tiles at a larger scale in a fixed row-major order. Compare the original with the candidate boundaries in this pass, assess each visible building entity rather than assigning a class to the tile, and reconcile additions, removals, and boundary contractions before publishing the preview. The overlap prevents losses at tile edges.
5. Log each correction by image. Promote a feedback rule into this skill only after it improves the reviewed result in at least three distinct TIFFs without recurrent counterexamples. Keep single-image or conflicting feedback as a local note; do not generalize it.
6. Stop automatic iteration when the next decision depends on obscured roofs, uncertain shadows, or the user’s local definition of high-rise. Mark these as `review` rather than guessing.

## From preview to QGIS

AI-edited preview pixels are not precise GIS geometry. To create a review layer, derive polygons from a georeferenced building-footprint source or manually draw/edit them in QGIS against the original GeoTIFF. Preserve these fields:

```text
image_id, candidate_id, class_suggested, evidence_visual,
evidence_height, source, confidence, review_status
```

For the one-SHP-per-TIFF workflow, use `class_id=1`, `class_name=highrise_residential`, an `object_id`, provenance, confidence, and review status. Pair that SHP with the original GeoTIFF for vector segmentation training. Only QGIS-confirmed polygons may be promoted from `qgis_review` to final training labels.

## Shanghai output layout

For the user's full-coverage binary review format, encode `class_id=1` / `class_name=highrise` for the building entities and `class_id=0` / `class_name=other` for the source TIFF extent minus their union. Save both classes in the same SHP with no gaps or overlaps, plus a same-basename QML categorized style. Use yellow for 1 and light blue for 0, both with 95% fill transparency (5% opacity); retain thin yellow building outlines. Render review examples from the actual vectors against the original TIFF. After QGIS additions, deletions, or boundary edits, recompute class 0 as the complement of class 1 before training. Transparency is display styling; class values remain integer 0 and 1. Back up existing Shapefile components before converting their coverage.

For Shanghai work, mirror the source TIFF hierarchy exactly under `tif_image_shanghai_标注`. Keep the Shapefile basename identical to its TIFF basename, and keep its `.shp`, `.shx`, `.dbf`, `.prj`, and `.cpg` companions together. For example:

```text
tif_image_shanghai/徐汇区/SH-XH-0207_梅陇五村高层/2010-2014__SH-XH-GREEN-0086_201404.tif
tif_image_shanghai_标注/徐汇区/SH-XH-0207_梅陇五村高层/2010-2014__SH-XH-GREEN-0086_201404.shp
```

Do not mix labels from different TIFFs into one layer or add image copies to the label directory.

## Community processing order

Treat each uniquely numbered community directory as one annotation unit. Process the TIFFs inside that directory in chronological filename order and complete its full time series before moving to the next community identifier. The first Shanghai unit is `SH-HK-0001_瑞虹新城一期`; its four TIFFs produce four same-basename Shapefiles in the mirrored `虹口区/SH-HK-0001_瑞虹新城一期` label directory.

## Combining data sources

3D-GloBFP and CMAB heights are useful for proposing or prioritizing candidates, but are estimates with time and boundary differences. Never remove a visually obvious tower merely because one height product misses it; instead assign `review`. Conversely, never accept a height-only polygon without checking its image alignment.

## Batch limits

Do not apply a visual preview directly to every image as final labels. First obtain user review across dense urban, ordinary residential, commercial, industrial, and low-rise contexts. Batch outputs must remain candidate layers and retain their evidence/provenance fields.

## Annotation versus later model training

The visual workflow identifies individual building entities, not a land-use class for each image tile. Tiling is a quality-control viewing method only. Each accepted entity remains one high-rise-residential polygon in the same-image SHP. For later semantic-segmentation training, pair the original GeoTIFF with the reviewed SHP, rasterize the polygons into a binary high-rise mask, and optionally cut the image and mask together into overlapping training tiles. The trained model then predicts pixels/masks rather than a single label for a whole tile.
