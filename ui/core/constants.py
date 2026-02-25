LLM_PROVIDER_PRESETS = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model_name": "deepseek-chat",
        "embedding_model": "text-embedding-3-small",
        "force_fake_embeddings": True,
    },
    "alibaba": {
        "label": "Alibaba Tongyi",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_name": "qwen-plus",
        "embedding_model": "text-embedding-v4",
        "force_fake_embeddings": False,
    },
    "bytedance": {
        "label": "Bytedance Doubao",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model_name": "doubao-pro-32k-241215",
        "embedding_model": "doubao-embedding-text-240715",
        "force_fake_embeddings": False,
    },
    "custom": {
        "label": "Custom OpenAI Compatible",
        "base_url": "",
        "model_name": "gpt-4o-mini",
        "embedding_model": "text-embedding-3-small",
        "force_fake_embeddings": False,
    },
}

