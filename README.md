# FastFoodOrderingAgent   :calling: :arrow_right: &#x1F916; :arrow_right: :hamburger: :fries:
A prototype application enabling users to issue voice or text commands to create and send a food order to fast food company sites. McDonald's site will be supported first.

[Project Management Crash Site Doc](https://docs.google.com/document/d/13NI7L9T9Er9HpxaoRiZk-KD-j6lIgyttm02fnWIr62I/edit?tab=t.0): where all our links go during this application's development.

## Application Set-up

    cp .env.template .env
    . scripts/install-cuda.sh
    . scripts/install-docker.sh
    . scripts/download-llamacpp-gguf.sh
    docker compose build
    docker compose up -d

Then go to http://localhost:10000/ to view application logs.

## Frontend Set-up

### Docker Build

    cd ui
    docker compose build

### Local Development

    cd ui
    npm install
    npm run dev

## Backend Set-up

### Docker Build

    cd python/fastfoodordering
    docker compose build

### Local Development

    cd python/fastfoodordering
    wget -qO- https://astral.sh/uv/install.sh | sh
    uv sync

### Possible Models List

**GGUF-formatted Vision-capable Models**:

- [MiniCPM-V-4_5](https://huggingface.co/openbmb/MiniCPM-V-4_5-gguf/tree/main) (tested, strong)
- [UI-TARS-1.5-7B](https://huggingface.co/mradermacher/UI-TARS-1.5-7B-GGUF/tree/main) or [other quantized versions](https://huggingface.co/models?other=base_model:quantized:ByteDance-Seed/UI-TARS-1.5-7B) (all untested)
- [UI-TARS-7B-DPO](https://huggingface.co/bartowski/UI-TARS-7B-DPO-GGUF/tree/main) (untested)
- [InternVL3_5-8B](https://huggingface.co/bartowski/OpenGVLab_InternVL3_5-8B-GGUF/tree/main) (untested)

**Text-only GGUF**, but may be worth looking into:
- [Qwen3-1.7B](https://huggingface.co/bartowski/Qwen_Qwen3-1.7B-GGUF/tree/main) (maybe text-only?, untested)
- [Qwen3-4B-toolcalling-gguf-codex](https://huggingface.co/Manojb/Qwen3-4B-toolcalling-gguf-codex) (maybe text-only?, untested)
- [Mistral-7B-Instruct-v0.3](https://huggingface.co/MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF) (maybe text-only?, untested)

Models that **would have to be converted to GGUF** (all untested):

- [AgentCPM-GUI](https://huggingface.co/openbmb/AgentCPM-GUI)

**More places to look**:

- [HuggingFace Trending GGUF Models](https://huggingface.co/models?library=gguf&p=4&sort=trending)

