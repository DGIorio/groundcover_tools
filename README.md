# DGI Groundcover Tools
[![Blender](https://img.shields.io/badge/Blender-v5.2+-blue?logo=blender&logoColor=white)](https://www.blender.org/releases/5-2/)
[![GitHub release](https://img.shields.io/github/release/DGIorio/groundcover_tools?include_prereleases=&sort=semver&color=blue)](https://github.com/DGIorio/groundcover_tools/releases/)
[![License: GPL-3.0](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/DGIorio)

**DGI Groundcover Tools** is a Blender extension for **painting vegetation** —
grass, weeds, bushes, shrubs, flowers, trees and other **foliage** — directly
onto any surface with a brush.

Plants are built as lightweight **Geometry-Nodes instances** (billboard *cards*
scattered on a point cloud), so you can cover a whole terrain with thousands of
trees, blades of grass or bushes and still paint, edit and animate it smoothly.

## Features
- 🖌️ **Brush painting** on any surface (terrain, landscape, ground mesh) with an
  on-surface ring cursor.
- 🌳 **Any plant type** — load any texture from disk (or pick one already in Blender)
  as the card, so you can paint grass, bushes, trees, flowers or any foliage you like.
- ⚡ **Lightweight** — Geometry-Nodes instancing keeps huge scatters fast and
  low on memory, even with hundreds of thousands of cards.
- 🎯 **Even (Poisson) scatter** so plants don't clump, with **Density**,
  **Spacing** and **Flow** (paint speed) control.
- ⛰️ **Terrain-aware** — cards snap to the surface and follow slopes.
- 🧭 **Alignment** — keep cards upright, align to the surface normal, or use an
  averaged normal for smooth results on bumpy ground, plus **random yaw**.
- 📐 **Sizing** — equal, random, or non-uniform width/height (tall trees, wide
  bushes), with a min/max range; rescale placed cards afterwards too.
- 🧽 **Eraser** — remove cards within the brush (mode toggle or Ctrl-drag).
- 🍃 **Wind sway** — optional time-based animation driven by a material `speed`
  value.
- 🗂️ **Texture atlas** support — grid or strip pages baked to the card UVs.
- 🎨 **Ready material** — a new card comes with an alpha-clipped foliage material;
  just drop in your image.

## Requirements
- [Blender 4.2 or newer](https://www.blender.org/releases/5-2/) (developed against Blender 5.2)

## Installation
1. Download the latest `.zip` from the [Releases](https://github.com/DGIorio/groundcover_tools/releases/) page.
2. In Blender, go to `Edit > Preferences > Get Extensions > Install from Disk` and select the `.zip` (or drag the `.zip` onto the Blender window).
3. Enable **DGI Groundcover Tools** in the add-ons list.

## Location
- `Object menu / right-click > Add > Groundcover`

## Usage
### 1. Create a vegetation type
`Add > Groundcover` (or the **Add Groundcover** button in the **Groundcover**
sidebar, `N`). In the popup choose a **Card**:

- **New Card** — builds a card mesh with a ready **alpha-clipped material**.
  Pick an image already loaded in Blender, use **Open** to load one from disk,
  or leave both empty and drop your image into the `Card Texture` node later.
  For an **atlas**, choose **Grid** (columns × rows) or **Strip** (single row),
  set the dimensions and pick the **Page** (row-major, 0 = top-left);
  the matching UV is baked onto the card.
- **Use Existing** — instance any mesh object already in the scene (your own
  tree/bush model, an imported card, …).

Set the default size range and brush radius, and optionally enable **Wind Sway**
(a time-based animation; also written to the material's `speed` custom property).
Leave **Start Painting** on and click OK — the instancer is created, selected,
and the **Vegetation Paint** tool is activated.

### 2. Paint (Object Mode)
With an instancer active, pick the **Vegetation Paint** tool in the viewport
toolbar (`T`). A ring shows the brush on the surface. Drag to paint; **Ctrl-drag**
inverts the current Paint/Erase mode. Settings live in the tool header and the
**Groundcover** sidebar:

- **Mode** — Paint or Erase (Erase removes cards within the brush).
- **Radius / Density / Spacing / Flow** — brush size, cards per *dab* (one stamp
  of the brush), minimum cursor travel between dabs, and maximum dabs per second
  (lower = slower, more controlled painting).
- **Single Card** — place one card at the cursor instead of scattering.
- **Align** — Upright, per-card surface **Normal**, or **Average** (one normal
  for the whole dab, smoother on bumpy ground).
- **Random Yaw** — spin cards around their up axis for variety.
- **Size** — Equal (square), Random (width and height each random), or
  Non-uniform (separate width and height ranges — e.g. tall trees).

### 3. Resize placed cards (Edit Mode)
A card's size is stored on its point, so to resize plants you've already placed:
enter **Edit Mode** on the instancer, select the point(s) for the card(s), and
run **Scale Selected** — drag `Factor` in the redo panel (N menu). With nothing
selected it scales every card in the instancer; `Height Only` keeps the width.

## License
Released under the [GNU General Public License v3.0 or later](https://www.gnu.org/licenses/gpl-3.0).

## Support
If you find these tools useful, consider supporting development on [Ko-fi](https://ko-fi.com/DGIorio).

---

<sub>Keywords: Blender vegetation painter, foliage brush, grass / bush / tree
scatter, forest generator, billboard cards, Geometry Nodes instancing, terrain
scattering, game-style vegetation tool.</sub>
