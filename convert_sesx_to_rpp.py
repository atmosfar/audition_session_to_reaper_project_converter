import xml.etree.ElementTree as ET
import sys
import os
import colorsys
import rpp

def convert_sesx_to_rpp(sesx_file):
    # Parse the SESX file
    tree = ET.parse(sesx_file)
    root = tree.getroot()

    # Create root RPP element
    root_elem = rpp.Element('REAPER_PROJECT', ['0.1'])

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

            track_elem = rpp.Element('TRACK')
            track_elem.extend([
                ['NAME', track_name],
                ['PEAKCOL', str(track_colour)],
                ['MUTESOLO', str(mute), str(solo), '0'],
                ['VOLPAN', f"{volume:.6f}", f"{pan:.6f}", "-1.000"],
                ['REC', str(armed), '0', str(monitor), '0', '0', '0', '0', '0'],
                ['AUTOMODE', '0']  # Set automation mode to the default Trim/Read
            ])

            # Process track volume automation (post-fader)
            track_keyframes = get_volume_keyframes(audio_track, sample_rate)
            if track_keyframes:
                track_elem.append(create_volenv(track_keyframes, env_type='VOLENV2'))

            # Find audio clips in the track
            for audio_clip in audio_track.findall('audioClip'):
                item_elem = rpp.Element('ITEM') # create ITEM chunk

                # extract values from clip
                clip_name = audio_clip.get('name')
                start_point = int(audio_clip.get('startPoint')) / sample_rate  # Convert to seconds
                end_point = int(audio_clip.get('endPoint')) / sample_rate  # Convert to seconds
                length = end_point - start_point
                source_start_point = int(audio_clip.get('sourceInPoint')) / sample_rate
                volume, pan, mute = get_volume_mute_pan(audio_clip)
                keyframes = get_volume_keyframes(audio_clip, sample_rate)

                # Handle volume automation
                volpan_value = volume
                if keyframes:
                    item_elem.append(create_volenv(keyframes))
                    volpan_value = 1.0  # Use unity gain when envelope is present

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
                file_format = get_source_format(file_extension)


                item_elem.extend([
                    ['POSITION', f"{start_point:.6f}"],
                    ['LENGTH', f"{length:.6f}"],
                    ['SOFFS', f"{source_start_point:.6f}"],
                    ['FADEIN', str(fade_in_curve), f"{fade_in_time:.6f}", "0.0"],
                    ['FADEOUT', str(fade_out_curve), f"{fade_out_time:.6f}", "0.0"],
                    ['VOLPAN', f"{volpan_value:.6f}", f"{pan:.6f}", "1.0", "-1.0"],
                    ['MUTE', str(mute)],
                    ['NAME', clip_name],
                    rpp.Element('SOURCE', [file_format], [
                        ['FILE', file_path, '1']
                    ])
                ])
                track_elem.append(item_elem)

            root_elem.append(track_elem)

    return rpp.dumps(root_elem)

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

def convert_sesx_volume_to_volenv(v):
    # Converts SESX volume value to Reaper's VOLENV linear scale using 10th-order polynomial
    # Polynomial coefficients for v^10 down to v^0
    coeffs = [
        -2.09233708e+04, 1.21079132e+05, -3.04166739e+05, 4.35852234e+05,
        -3.94242081e+05, 2.35794282e+05, -9.52128435e+04, 2.61473496e+04,
        -4.91584283e+03, 6.76296702e+02, -7.34158940e+01
    ]

    # Calculate dB using polynomial evaluation
    original_dB = sum(c * (v ** (10 - i)) for i, c in enumerate(coeffs))

    # Clamp to Reaper's operational range and convert to linear scale
    dB_clamped = max(min(original_dB, 6), -60)
    volenv = 10 ** (dB_clamped / 20)

    # Ensure we don't exceed Reaper's maximum VOLENV value of 2.0
    return min(volenv, 2.0), original_dB

def get_volume_keyframes(audio_element, sample_rate):
    keyframes = []
    vol_component = audio_element.find(".//component[@componentID='Audition.Fader'][@name='volume']")
    if vol_component is not None:
        vol_param = vol_component.find(".//parameter[@name='volume']")
        if vol_param is not None:
            kf_container = vol_param.find('parameterKeyframes')
            if kf_container is not None:
                # Get sourceInPoint from the element itself
                source_in_point = int(audio_element.get('sourceInPoint', 0))
                
                for kf in kf_container.findall('parameterKeyframe'):
                    # Calculate absolute time then adjust by sourceInPoint
                    time_sec = (int(kf.get('sampleOffset')) - source_in_point) / sample_rate

                    sesx_value = float(kf.get('value'))
                    volenv_value, original_dB = convert_sesx_volume_to_volenv(sesx_value)
                    if original_dB > 6:
                        print(f"Warning: SESX volume keyframe value at {time_sec:.2f}s ({original_dB:.1f} dB) exceeds Reaper's +6 dB maximum")

                    curve_type = kf.get('type')

                    keyframes.append((
                        time_sec,
                        volenv_value,
                        curve_type
                    ))
    return keyframes

def create_volenv(keyframes, env_type='VOLENV'):
    shape_map = {
        'hold': 1,     # Square shape in Reaper
        'linear': 0,   # Linear shape
        'bezier': 5    # Bezier (if present)
    }

    vol_env = rpp.Element(env_type, [
        ['ACT', '1', '-1'],
        ['VIS', '1', '1', '1.0'],
        ['LANEHEIGHT', '0', '0'],
        ['ARM', '0'],
        ['DEFSHAPE', '0', '-1', '-1'],
        ['VOLTYPE', '1']
    ])

    for time, value, kf_type in keyframes:
        shape = shape_map.get(kf_type.lower(), 0) # Default to linear
        vol_env.append([
            'PT', 
            f"{time:.6f}", 
            f"{value:.6f}", 
            str(shape), 
            '0', '0', '0'
        ])
    return vol_env

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
