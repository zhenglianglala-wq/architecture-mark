# architecture-mark

面向遥感 RGB 影像的高层住宅候选标注工作流：Codex 视觉初标、人工颜色反馈、QGIS 可编辑矢量与二分类分割标签准备。

当前项目提供可复用 Codex skill 和两个辅助脚本。识别依据是可见建筑实体、立面、塔楼形态及阴影等视觉证据；输出是待精修的候选标注。它不测量建筑高度，也不单凭 RGB 确认住宅用途。阴影是识别线索，建筑边界沿可见实体描绘。

## 工作流程

1. 读取原始 GeoTIFF，逐栋识别高层住宅候选，绘制细黄色轮廓。
2. 初标后重新全图检查，再对重叠 3×3 或 4×4 分块放大检查漏标、误标及边界。
3. 将候选图交给人工审核：红色补入、绿色删除、蓝色收缩去除阴影或地面。反馈圈只指示位置。
4. 人工确认后，每张 TIF 保存一个同名 SHP，按区/小区镜像源目录。候选状态为 `qgis_review`。
5. 在 QGIS 修改建筑几何；修改完成后重新计算类别 0 的补集，再准备训练标签。
6. 在多种场景人工审核几十张、规则稳定且用户明确启动后，才批量生成候选标注。识别经验至少在三张不同影像验证后提升为通用规则。

分块用于逐栋检查。分割训练的目标是像素类别，而不是给整块影像赋一个建筑类别。

## 输出与显示

| 字段/类别 | 含义 |
|---|---|
| `class_id=1`, `class_name=highrise` | 高层建筑候选 |
| `class_id=0`, `class_name=other` | 影像范围减建筑面并集 |
| `image_id`, `object_id` | 影像及对象编号 |
| `source`, `confidence`, `lbl_status` | 来源、置信与审核状态 |

同一 SHP 包含 0/1 两类面，覆盖整个影像范围，无空隙和重叠。SHP 的 `.shx/.dbf/.prj/.cpg` 伴随文件需一起保存。同名 QML 提供 QGIS 分类显示：高层黄色，其他淡蓝色；两类填充 **95% 透明**，保留建筑细黄色边线。透明度只是显示样式，不改变整数 0/1 类别。

```text
tif_image_shanghai/<区>/<小区>/<日期编号>.tif
tif_image_shanghai_标注/<区>/<小区>/<日期编号>.shp
tif_image_shanghai_标注/<区>/<小区>/<日期编号>.qml
```

在 QGIS 同时加载原 TIF 和 SHP 即可检查并编辑；现有图层如未刷新样式，可手动加载同名 QML。增删建筑后应重算背景补集。

## 使用 skill

把 `skills/visual-highrise-annotation` 目录复制到本机 Codex 的 skills 目录，例如 `~/.codex/skills/`。重新打开对话后调用 `$visual-highrise-annotation`，同时告知实际源影像和输出目录。skill 中的上海目录及首个小区是本项目约定，可按你的任务调整。

skill 负责行为规则；具有图像生成工具的 Codex 环境可输出人工圈改画布。脚本本身不运行识别模型，也不独立提供画布界面。

## 辅助脚本

建议 Python 3.11+，安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

将人工确认的、完整范围的黄色轮廓预览转为建筑候选 SHP：

```bash
python inference/visual_preview_to_shp.py \
  --tif tif_image_shanghai/<区>/<小区>/<日期编号>.tif \
  --preview approved_preview.png \
  --tif-root tif_image_shanghai \
  --labels-root tif_image_shanghai_标注
```

在仓库根目录放置上述源/标签目录后，统一补充背景类别、备份已有文件、写入95%透明 QML，并从真实几何叠加原图渲染示例：

```bash
python inference/style_binary_labels.py
```

脚本处理已有 SHP，输出预览到 `highrise_residential_labels/binary_review`，备份到 `highrise_residential_labels/backups`。执行前保存并关闭 QGIS 正在编辑的图层。

## 精度和适用范围

当前脚本按 north-up、EPSG:4326、含 ModelTiepointTag 和 ModelPixelScaleTag 的 RGB GeoTIFF 实现；其他投影、旋转栅格、无效像元须先适配处理。黄色轮廓转换是近似：生成预览可能变形、边缘轮廓不闭合、轮廓提取遗漏或合并。必须在原 TIF 上检查最终矢量位置与建筑边界，QGIS 精修后再作为训练真值。几何有效及覆盖率100%只检验拓扑，不代表识别准确。

训练时以原 TIF 为参考网格栅格化 QGIS 确认的类别，随后同步切分影像与 mask。3D-GloBFP、CMAB 等高度产品可作为额外证据，但当前工作流不要求它们。

仓库发布内容为规则和代码。项目影像与标注数据由使用者自行准备。
