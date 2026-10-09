"""Add explicit class-0 coverage and a transparent QGIS style to reviewed SHPs."""
from pathlib import Path
from datetime import datetime
import os
import shutil
import tempfile
import argparse
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import tifffile
from PIL import Image, ImageDraw
from shapely.geometry import box, Polygon, MultiPolygon, GeometryCollection
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
LABELS = ROOT / 'tif_image_shanghai_标注'
SOURCES = ROOT / 'tif_image_shanghai'
PREVIEWS = ROOT / 'highrise_residential_labels/binary_review'

def polygons(geometry):
    if isinstance(geometry, Polygon):
        return [geometry]
    if isinstance(geometry, (MultiPolygon, GeometryCollection)):
        return [p for g in geometry.geoms for p in polygons(g)]
    return []

def write_style(path):
    qgis = ET.Element('qgis', version='3.40', styleCategories='Symbology')
    renderer = ET.SubElement(qgis, 'renderer-v2', type='categorizedSymbol', attr='class_id', symbollevels='0', enableorderby='0')
    categories = ET.SubElement(renderer, 'categories')
    symbols = ET.SubElement(renderer, 'symbols')
    for value, label, color in [('0', '其他 (0)', '100,170,255,13'), ('1', '高层建筑 (1)', '255,230,0,13')]:
        ET.SubElement(categories, 'category', value=value, label=label, symbol=value, render='true', type='int')
        symbol = ET.SubElement(symbols, 'symbol', name=value, type='fill', alpha='1', clip_to_extent='1')
        layer = ET.SubElement(symbol, 'layer', **{'class': 'SimpleFill', 'enabled': '1', 'locked': '0', 'pass': '0'})
        options = ET.SubElement(layer, 'Option', type='Map')
        props = {'color': color, 'style': 'solid', 'outline_style': 'solid' if value == '1' else 'no', 'outline_color': '255,230,0,255', 'outline_width': '0.25', 'outline_width_unit': 'MM', 'joinstyle': 'miter'}
        for name, val in props.items():
            ET.SubElement(options, 'Option', name=name, value=val, type='QString')
    ET.SubElement(qgis, 'layerOpacity').text = '1'
    ET.ElementTree(qgis).write(path, encoding='UTF-8', xml_declaration=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--shp', type=Path, help='Process only this Shapefile')
    args = parser.parse_args()
    backup = ROOT / 'highrise_residential_labels/backups' / datetime.now().strftime('binary_%Y%m%d_%H%M%S')
    targets = [args.shp.resolve()] if args.shp else sorted(LABELS.rglob('*.shp'))
    for shp in targets:
        rel = shp.relative_to(LABELS)
        tif = (SOURCES / rel).with_suffix('.tif')
        if not tif.exists():
            raise RuntimeError(f'Missing source: {tif}')
        original = gpd.read_file(shp)
        if original.crs.to_epsg() != 4326:
            raise RuntimeError(f'Unexpected CRS: {shp}')
        buildings = original[original.class_id == 1].copy()
        with tifffile.TiffFile(tif) as f:
            page = f.pages[0]
            arr = page.asarray()
            h, w = arr.shape[:2]
            tie = page.tags['ModelTiepointTag'].value
            scale = page.tags['ModelPixelScaleTag'].value
            west, north = tie[3] - tie[0]*scale[0], tie[4] + tie[1]*scale[1]
            dx, dy = scale[:2]
        extent = box(west, north-h*dy, west+w*dx, north)
        buildings.geometry = buildings.geometry.intersection(extent)
        union = unary_union(buildings.geometry)
        background = extent.difference(union)
        records = buildings.to_dict('records')
        for record in records:
            record['class_name'] = 'highrise'
        for polygon in polygons(background):
            records.append({'image_id': shp.stem, 'object_id': len(records)+1, 'class_id': 0, 'class_name': 'other', 'source': 'extent_diff', 'confidence': 'derived', 'lbl_status': 'qgis_review', 'geometry': polygon})
        result = gpd.GeoDataFrame(records, crs=original.crs)
        if not result.is_valid.all():
            raise RuntimeError(f'Invalid geometry: {shp}')
        covered = unary_union(result.geometry)
        if covered.symmetric_difference(extent).area > extent.area * 1e-8:
            raise RuntimeError(f'Coverage mismatch: {shp}')
        if abs(sum(geom.area for geom in result.geometry)-extent.area) > extent.area * 1e-8:
            raise RuntimeError(f'Overlapping labels: {shp}')
        saved = backup / rel.parent
        saved.mkdir(parents=True, exist_ok=True)
        for suffix in ('.shp','.shx','.dbf','.prj','.cpg','.qml'):
            component = shp.with_suffix(suffix)
            if component.exists():
                shutil.copy2(component, saved / component.name)
        with tempfile.TemporaryDirectory(dir=ROOT) as stage:
            staged = Path(stage) / shp.name
            result.to_file(staged, driver='ESRI Shapefile', encoding='UTF-8')
            check = gpd.read_file(staged)
            assert set(check.class_id) == {0,1} and check.is_valid.all()
            for component in Path(stage).iterdir():
                shutil.copy2(component, shp.parent / component.name)
        write_style(shp.with_suffix('.qml'))
        # Render deterministically from the actual vectors on the original TIFF.
        image = Image.fromarray(arr[:,:,:3].astype(np.uint8)).convert('RGBA')
        overlay = Image.new('RGBA', image.size, (0,0,0,0))
        def coords(ring):
            return [((x-west)/dx, (north-y)/dy) for x,y in ring.coords]
        for _, row in result.iterrows():
            mask = Image.new('L', image.size, 0)
            draw = ImageDraw.Draw(mask)
            for poly in polygons(row.geometry):
                draw.polygon(coords(poly.exterior), fill=13)
                for hole in poly.interiors:
                    draw.polygon(coords(hole), fill=0)
            color = (255,230,0,0) if row.class_id == 1 else (100,170,255,0)
            layer = Image.new('RGBA', image.size, color)
            layer.putalpha(mask)
            overlay = Image.alpha_composite(overlay, layer)
        image = Image.alpha_composite(image, overlay)
        draw = ImageDraw.Draw(image)
        for geom in buildings.geometry:
            for poly in polygons(geom):
                draw.line(coords(poly.exterior), fill=(255,230,0,255), width=1)
        preview = (PREVIEWS / rel).with_suffix('.png')
        preview.parent.mkdir(parents=True, exist_ok=True)
        image.convert('RGB').save(preview)
        print(f'{rel}: highrise={len(buildings)}, other={len(result)-len(buildings)}, coverage=100%, fill_transparency=95%')
    print(f'Backup: {backup}')

if __name__ == '__main__':
    main()
