## API Key

Đặt trong biến môi trường `VILAO_API_KEY` (xem `.env.example`). **Không commit key vào repo** — mọi key phát hiện trong git history phải được rotate ngay trên console.

## Endpoint

Base URL: `https://api.vilao.ai/v1`

POST
`https://api.vilao.ai/v1/chat/completions`

POST
`https://api.vilao.ai/v1/responses`

POST
`https://api.vilao.ai/v1/messages`

POST
`https://api.vilao.ai/v1/embeddings`

POST
`https://api.vilao.ai/v1/images/generations`

POST
`https://api.vilao.ai/v1/images/edits`

POST
`https://api.vilao.ai/v1/audio/speech
`
POST
`https://api.vilao.ai/v1/audio/transcriptions`

POST
`https://api.vilao.ai/v1/audio/translations`

POST
`https://api.vilao.ai/v1/videos`

GET
`https://api.vilao.ai/v1/videos/:id`

GET
`https://api.vilao.ai/v1/videos/:id/content`

GET
`https://api.vilao.ai/v1/models`

## Tên model dùng trong API

- `gx/gpt-5.4`
- `imx/gpt-image-2`

## cURL — Chat

```
curl https://api.vilao.ai/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gx/gpt-5.4","messages":[{"role":"user","content":"Hello!"}]}'
```

### cURL — Responses (OpenAI)

```
curl https://api.vilao.ai/v1/responses \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"gx/gpt-5.4","input":"Hello!"}'
```

### cURL — Image Generation

```
curl https://api.vilao.ai/v1/images/generations \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"imx/gpt-image-2","prompt":"A cute red panda sitting on a tree branch, soft sunlight, photorealistic.","n":1,"size":"auto"}' \
  -o image.json
```

### cURL — Image Edits (multipart)

```
curl https://api.vilao.ai/v1/images/edits \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "model=imx/gpt-image-2" \
  -F "image=@./input.png" \
  -F "mask=@./mask.png" \
  -F "prompt=Add a small hat to the panda" \
  -F "size=auto"
```

### Python — Chat (openai SDK)

```
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://api.vilao.ai/v1"
)

response = client.chat.completions.create(
    model="gx/gpt-5.4",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response.choices[0].message.content)
```

### Python — Responses (openai SDK)

```
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://api.vilao.ai/v1"
)

response = client.responses.create(
    model="gx/gpt-5.4",
    input="Hello!"
)
print(response.output_text)

Python — Image Generation (openai SDK)
import base64
from openai import OpenAI

client = OpenAI(
    api_key="YOUR_API_KEY",
    base_url="https://api.vilao.ai/v1"
)

result = client.images.generate(
    model="imx/gpt-image-2",
    prompt="A cute red panda sitting on a tree branch, soft sunlight, photorealistic.",
    size="auto",
    n=1,
)

# response_format: b64_json (default for some models) hoặc url
item = result.data[0]
if getattr(item, "b64_json", None):
    with open("image.png", "wb") as f:
        f.write(base64.b64decode(item.b64_json))
    print("Saved image.png")
else:
    print(item.url)
```