
import openai

client = openai.AsyncOpenAI(
    base_url="http://kokoro-tts:8880/v1", api_key="not-needed"
)

async def create_audio_file_docker(text: str, title: str):
    fname = f'{title}.mp3'
    response = await client.audio.speech.create(
        model="kokoro",
        voice="af_bella", #single or multiple voicepack combo
        input=text
      )
    response.write_to_file(fname)
    return fname