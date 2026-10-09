#!/usr/bin/env python3
"""Convert an approved visual annotation preview into a QGIS SHP layer.

The visual preview must have thin yellow building outlines over the unchanged
image. The polygons are georeferenced to the supplied GeoTIFF and represent
the visible physical building boundary. Labels remain editable in QGIS.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Use a Python environment with a valid PROJ installation.
import geopandas as gpd
import numpy as np
import tifffile
from PIL import Image
from scipy import ndimage as ndi
from shapely.geometry import Polygon
from skimage.measure import find_contours


CLASS_ID = 1
CLASS_NAME = "highrise_residential"


def yellow_outline_mask(rgb: np.ndarray) -> np.ndarray:
    """Select the unfilled yellow candidate outlines used in the preview."""
    r, g, b = (rgb[..., i].astype(np.int16) for i in range(3))
    return (r > 200) & (g > 170) & (b < 100) & ((r - b) > 130)


def contour_to_polygon(component: np.ndarray, scale_x: float, scale_y: float) -> tuple[Polygon, list[float]] | None:
    """Return the largest outer contour in raw-TIFF pixel coordinates."""
    contours = find_contours(component.astype(np.uint8), 0.5)
    if not contours:
        return None
    contour = max(contours, key=len)
    # find_contours gives (row, col); COCO/QGIS pixel geometry uses (x, y).
    xy = np.column_stack((contour[:, 1] * scale_x, contour[:, 0] * scale_y))
    if len(xy) < 4:
        return None
    polygon = Polygon(xy)
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.geom_type != "Polygon" or polygon.area < 8:
        return None
    return polygon, xy.ravel().round(2).tolist()


def pixel_polygon_to_geo(pixel_polygon: Polygon, west: float, north: float, px_w: float, px_h: float) -> Polygon:
    def convert(coords):
        return [(west + x * px_w, north - y * px_h) for x, y in coords]

    return Polygon(convert(pixel_polygon.exterior.coords))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tif", type=Path, required=True, help="Source GeoTIFF")
    parser.add_argument("--preview", type=Path, required=True, help="Approved full-extent yellow-outline PNG")
    parser.add_argument("--output-dir", type=Path, help="Directory for one TIFF's SHP label")
    parser.add_argument("--image-id", help="Output SHP basename; defaults to the TIFF basename")
    parser.add_argument("--tif-root", type=Path, help="Source TIFF root for mirrored output")
    parser.add_argument("--labels-root", type=Path, help="Destination root for mirrored output")
    parser.add_argument("--write-metadata", action="store_true", help="Also write a JSON metadata sidecar")
    args = parser.parse_args()

    if not args.tif.is_file() or not args.preview.is_file():
        raise SystemExit("The TIFF and preview must both exist.")
    if bool(args.tif_root) != bool(args.labels_root):
        raise SystemExit("Use --tif-root and --labels-root together, or use --output-dir.")
    if args.tif_root:
        try:
            relative_tif = args.tif.resolve().relative_to(args.tif_root.resolve())
        except ValueError as exc:
            raise SystemExit("The TIFF must be inside --tif-root.") from exc
        output_dir = args.labels_root / relative_tif.parent
        image_id = args.image_id or relative_tif.stem
    else:
        if args.output_dir is None:
            raise SystemExit("Provide --output-dir or the --tif-root/--labels-root pair.")
        output_dir = args.output_dir
        image_id = args.image_id or args.tif.stem
    # A community directory holds one Shapefile per dated TIFF.  Protect only
    # the target image's complete Shapefile family, so earlier dates remain
    # untouched while the next date can be added beside them.
    target_stem = output_dir / image_id
    existing_target = [
        path
        for suffix in (".shp", ".shx", ".dbf", ".prj", ".cpg")
        if (path := target_stem.with_suffix(suffix)).exists()
    ]
    if existing_target:
        raise SystemExit(
            "Refusing to overwrite existing target Shapefile components: "
            + ", ".join(str(path) for path in existing_target)
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    with tifffile.TiffFile(args.tif) as tif:
        page = tif.pages[0]
        tags = page.tags
        array = page.asarray()
        height, width = array.shape[:2]
        geo = tags["ModelTiepointTag"].value
        scale = tags["ModelPixelScaleTag"].value
        # The supplied TIFFs use a north-up, geographic affine transform.
        west, north = float(geo[3]), float(geo[4])
        px_w, px_h = float(scale[0]), float(scale[1])
        epsg = "EPSG:4326"

    preview = np.asarray(Image.open(args.preview).convert("RGB"))
    preview_h, preview_w = preview.shape[:2]
    scale_x, scale_y = width / preview_w, height / preview_h

    outlines = yellow_outline_mask(preview)
    labels, count = ndi.label(outlines)
    records: list[dict] = []
    for index in range(1, count + 1):
        outline = labels == index
        if int(outline.sum()) < 200:
            continue
        # Close anti-aliased one-pixel breaks, then fill only this outline.
        roof = ndi.binary_dilation(outline, iterations=1)
        roof = ndi.binary_closing(roof, iterations=1)
        roof = ndi.binary_fill_holes(roof)
        converted = contour_to_polygon(roof, scale_x, scale_y)
        if converted is None:
            continue
        pixel_poly, _ = converted
        geo_poly = pixel_polygon_to_geo(pixel_poly, west, north, px_w, px_h)
        records.append(
            {
                "image_id": image_id,
                "object_id": len(records) + 1,
                "class_id": CLASS_ID,
                "class_name": CLASS_NAME,
                "source": "visual_iter02",
                "confidence": "user_approved",
                "lbl_status": "qgis_review",
                "geometry": geo_poly,
            }
        )

    if not records:
        raise SystemExit("No closed yellow roof outlines were detected; no SHP created.")

    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs=epsg)
    shp_path = output_dir / f"{image_id}.shp"
    gdf.to_file(shp_path, driver="ESRI Shapefile", encoding="UTF-8")
    if args.write_metadata:
        metadata = {
            "image_id": image_id,
            "source_tif": str(args.tif.resolve()),
            "label_file": str(shp_path.resolve()),
            "geometry": "visible physical building polygon",
            "class_map": {"1": CLASS_NAME},
            "feature_count": len(gdf),
            "crs": epsg,
            "training_pair": "Use the original GeoTIFF with this same-image SHP after QGIS review.",
        }
        (output_dir / f"{image_id}_metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(f"Wrote {len(gdf)} {CLASS_NAME} polygons to {shp_path}")


if __name__ == "__main__":
    main()
