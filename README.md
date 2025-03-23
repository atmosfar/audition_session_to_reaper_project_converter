# Audition session to Reaper project converter

This script provides basic conversion between Adobe Audition Session (.sesx) files and Reaper Project (.rpp) files.

## Supported features
- Track name
- Track colour
- Track mute, volume, pan
- Clip position and length
- Clip crossfading
- Clip mute, volume, pan

## Usage

```bash
python convert_sesx_to_rpp.py /path/to/audition_session.sesx
```
The script will generate a new .rpp file in the same directory with the same name.

## Contributing
Session files are structured as XML, so the main effort is finding and matching the correct names between the data field of interest, and the corresponding [chunk name](https://github.com/ReaTeam/Doc/blob/master/State%20Chunk%20Definitions) in the Reaper project file.
