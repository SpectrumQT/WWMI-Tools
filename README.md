<h1 align="center">WWMI Tools</h1>

<h4 align="center">Blender addon for Wuthering Waves Model Importer</h4>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#how-to-use">How To Use</a> • 
  <a href="#assets">Assets</a> •
  <a href="#installation">Installation</a> •
  <a href="#resources">Resources</a> •
  <a href="#license">License</a>
</p>

## Known Issues

- Glitch with duplicate modded objects on screen (Merged Skeleton hard limitation, won't be fixed)

## Features  

- **Frame Dump Data Extraction** — Fully automatic objects extraction from WuWa frame dumps
- **Extracted Object Import** —Imports extracted object into Blender as fully editable mesh
- **WWMI Mod Export** — Builds plug-and-play WWMI-compatible mod out of mesh components
- **Bones Merging** — Automatically merges VG lists merging and joins duplicates 
- **Shape Keys Support** — Automatically handles original shape keys and supports custom ones
- **Customizable Export** — Fast template-powered mod export engine with per-buffer export support

## How To Use

All fields and actions of the plugin have basic tooltips. Refer to [Modder Guide](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/guides/modder_guide.md) for more details.

## Assets  

Already dumped and exported models are located in [WWMI Assets](https://github.com/SpectrumQT/WWMI-Assets) repository.

## Installation

1. Install [the latest Blender version](https://www.blender.org/download/) (**tested with up to v5.0**)
2. Download the [latest release](https://github.com/SpectrumQT/WWMI-Tools/releases/latest) of **WWMI-Tools-X.X.X.zip**
3. Open Blender, go to **[Edit] -> [Preferences] -> [Add-ons]**
4. Open addon `.zip` selection dialogue via top-right corner button:
    * For **Blender 3.6 LTS**: Press **[Install]** button
    * For **Blender 4.X**: Press **[V]** button and select **Install from Disk...**
5. Locate downloaded **WWMI-Tools-X.X.X.zip** and select it
6. Press **[Install Addon]** button
7. Start typing  **WWMI** to filter in top-right corner
8. Tick checkbox named **Object: WWMI Tools** to enable addon

![wwmi-tools-installation](https://github.com/SpectrumQT/WWMI-TOOLS/blob/main/public-media/Installation.gif)

## Resources

- [XXMI Launcher](https://github.com/SpectrumQT/XXMI-Launcher)
- [WWMI GitHub](https://github.com/SpectrumQT/WWMI) ([Mirror: Gamebanana](https://gamebanana.com/tools/17252))
- [WWMI Tools GitHub (you're here)] ([Mirror: Gamebanana](https://gamebanana.com/tools/17289))
- [WWMI Assets](https://github.com/SpectrumQT/WWMI-Assets)
  
## License

WWMI Tools is licensed under the [GPLv3 License](https://github.com/SpectrumQT/WWMI-Tools/blob/main/LICENSE).
