# Audition session to Reaper project converter

This script provides basic conversion between Adobe Audition Session (.sesx) files and Reaper Project (.rpp) files.

## Supported features⏎
Tracks:
- Name
- Colour
- Mute / Volume / Pan
- Solo / Record / Monitor
Clip:
- Position and length
- Crossfading
- Mute / Volume / Pan

## Usage

```bash
python convert_sesx_to_rpp.py /path/to/audition_session.sesx
```
The script will generate a new .rpp file in the same directory with the same name.

## Contributing
Session files are structured as XML, so the main effort is finding and matching the correct names between the data field of interest, and the corresponding [chunk name](https://github.com/ReaTeam/Doc/blob/master/State%20Chunk%20Definitions) in the Reaper project file.
