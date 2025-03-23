import xml.etree.ElementTree as ET
import sys
import os
import colorsys

def convert_sesx_to_rpp(sesx_file):
    # Parse the SESX file
    tree = ET.parse(sesx_file)
    root = tree.getroot()

    # Prepare the output RPP content
    rpp_content = "<REAPER_PROJECT 0.1\n"

    # Get the sample rate from the session properties
    session = root.find('.//session')
    sample_rate = int(session.get('sampleRate', 48000))  # Default to 48000 if not found

    # Find the tracks in the SESX file
    tracks = root.find('.//tracks')
    if tracks is not None:
        for audio_track in tracks.findall('audioTrack'):
            track_name = audio_track.find('trackParameters/name').text

            track_hue = int(audio_track.find('trackParameters').get('trackHue', 0))
            track_colour = hue_to_peakcol(track_hue)

            volume, pan, mute = get_volume_mute_pan(audio_track)

            audio_params = audio_track.find('trackAudioParameters')
            solo = get_track_audio_param(audio_params, "solo")
            armed = get_track_audio_param(audio_params, "recordArmed")
            monitor = get_track_audio_param(audio_params, "monitoring")

            rpp_content += f"  <TRACK\n    NAME \"{track_name}\"\n"
            rpp_content += f"    PEAKCOL {track_colour}\n"
            rpp_content += f"    MUTESOLO {mute} {solo} 0\n"
            rpp_content += f"    VOLPAN {volume} {pan} -1.000\n"
            rpp_content += f"    REC {armed} 0 {monitor} 0 0 0 0 0\n"

            # Find audio clips in the track
            for audio_clip in audio_track.findall('audioClip'):
                clip_name = audio_clip.get('name')
                start_point = int(audio_clip.get('startPoint')) / sample_rate  # Convert to seconds
                end_point = int(audio_clip.get('endPoint')) / sample_rate  # Convert to seconds
                length = end_point - start_point
                source_start_point = int(audio_clip.get('sourceInPoint')) / sample_rate
                volume, pan, mute = get_volume_mute_pan(audio_clip)

                # Fade in details
                fade_in = audio_clip.find('fadeIn')
                fade_in_time = 0.0
                fade_in_curve = 0
                if fade_in is not None:
                    fade_in_start = int(fade_in.get('startPoint')) / sample_rate
                    fade_in_end = int(fade_in.get('endPoint')) / sample_rate
                    fade_in_time = fade_in_end - fade_in_start
                    fade_in_curve = fade_type_to_curve(fade_in.get('type'))

                # Fade out details
                fade_out = audio_clip.find('fadeOut')
                fade_out_time = 0.0
                fade_out_curve = 0
                if fade_out is not None:
                    fade_out_start = int(fade_out.get('startPoint')) / sample_rate
                    fade_out_end = int(fade_out.get('endPoint')) / sample_rate
                    fade_out_time = fade_out_end - fade_out_start
                    fade_out_curve = fade_type_to_curve(fade_out.get('type'))

                # Find the corresponding file
                file_id = audio_clip.get('fileID')
                file_element = root.find(f".//file[@id='{file_id}']")
                file_path = file_element.get('absolutePath')
                file_extension = os.path.splitext(file_path)[1][1:].upper()  
                file_format = get_source_format(file_extension);


                rpp_content += f"    <ITEM\n"
                rpp_content += f"      POSITION {start_point}\n"
                rpp_content += f"      LENGTH {length}\n"
                rpp_content += f"      SOFFS {source_start_point}\n"
                rpp_content += f"      FADEIN {fade_in_curve} {fade_in_time} 0.0\n"
                rpp_content += f"      FADEOUT {fade_out_curve} {fade_out_time} 0.0\n"
                rpp_content += f"      VOLPAN {volume} {pan} 1.0 -1.0\n"
                rpp_content += f"      MUTE {mute}\n"
                rpp_content += f"      NAME {clip_name}\n"
                rpp_content += f"      <SOURCE {file_format}\n        FILE \"{file_path}\" 1\n      >\n"
                rpp_content += "    >\n"

            rpp_content += "  >\n"

    rpp_content += ">\n"

    return rpp_content

def fade_type_to_curve(fade_type):
    # Map fade type to Reaper fade curve type
    match fade_type:
        case "lin":
            return 0
        case "log":
            return 1
    return 0

def hue_to_peakcol(track_hue):
    # Convert HSL (track_hue, 100%, 100%) to RGB

    hue = track_hue % 360 / 360
    saturation = 0.5 # default level for track legibility
    value = 1.0

    r, g, b = colorsys.hsv_to_rgb(hue, saturation, value)
    red = int(255 * r)
    green = int(255 * g)
    blue = int(255 * b)

    # Create PEAKCOL integer
    peakcol = (0x1 << 24) | (blue << 16) | (green << 8) | red

    return peakcol

def get_source_format(file_extension):
    match file_extension.lower():
        case "wav":
            return "WAVE"
        case "mp3":
            return "MP3"
        case "m4a" | "mp4" | "aac":
            return "VIDEO"
        case "flac":
            return "FLAC"

def get_track_audio_param(audio_params, param_name):
    # Initialize default value
    param_value = audio_params.get(param_name, 0)
    print(f"{param_name}: {param_value}")
    if param_value != 0:
        if param_value == "true":
            param_value = 1 
    return param_value

def get_volume_mute_pan(audio_element):
    # Initialize default values
    volume = 1.0  # Default volume (0 dB)
    pan = 0.0     # Default pan (center)
    mute = 0      # Default mute (not muted)

    # Extract volume from audio element
    volume_component = audio_element.find(".//component[@componentID='Audition.Fader'][@name='volume']")
    if volume_component is not None:
        volume_param = volume_component.find(".//parameter[@name='volume']")
        if volume_param is not None:
            volume = float(volume_param.get('parameterValue', 1.0))

    # Extract mute from audio element (if applicable)
    mute_component = audio_element.find(".//component[@componentID='Audition.Mute']")
    if mute_component is not None:
        mute_param = mute_component.find(".//parameter[@name='mute']")
        if mute_param is not None:
            mute = int(mute_param.get('parameterValue', 0))

    # Extract pan from audio element (if applicable)
    pan_component = audio_element.find(".//component[@componentID='Audition.StereoPanner']")
    if pan_component is not None:
        pan_param = pan_component.find(".//parameter[@name='Pan']")
        if pan_param is not None:
            pan = float(pan_param.get('parameterValue', 0.0)) / 100

    return volume, pan, mute

def main():
    if len(sys.argv) != 2:
        print("Usage: python convert_sesx_to_rpp.py <input.sesx>")
        sys.exit(1)

    sesx_file = sys.argv[1]
    if not os.path.isfile(sesx_file):
        print(f"File not found: {sesx_file}")
        sys.exit(1)

    rpp_content = convert_sesx_to_rpp(sesx_file)

    # Create the output RPP file name
    rpp_file = os.path.splitext(sesx_file)[0] + '.rpp'
    with open(rpp_file, 'w') as f:
        f.write(rpp_content)

    print(f"Converted {sesx_file} to {rpp_file}")

if __name__ == "__main__":
    main()

