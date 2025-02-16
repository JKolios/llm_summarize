from kokoro import KPipeline
import soundfile

pipeline = KPipeline(lang_code='a') # <= make sure lang_code matches voice

def create_audio_file(text: str, title: str):
    generator = pipeline(text, voice='af_heart', speed=1)
    fname = f'{title}.mp3'
    with soundfile.SoundFile(f'{title}.mp3', format="mp3", mode='x', samplerate=24000, bitrate_mode='CONSTANT', compression_level=0, channels=1) as sound_file:
        for i, (_, _, audio) in enumerate(generator):
            sound_file.write(audio)
    return fname

