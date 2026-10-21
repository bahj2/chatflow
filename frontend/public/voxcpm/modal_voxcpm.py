import modal

app = modal.App("replyflow-voxcpm2")
cache = modal.Volume.from_name("replyflow-voxcpm2-cache", create_if_missing=True)
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg", "libsndfile1")
    .pip_install("voxcpm", "fastapi[standard]", "soundfile")
    .env({"HF_HOME": "/cache/hf"})
    .add_local_file("voxcpm_server.py", "/root/voxcpm_server.py")
)


@app.cls(image=image, gpu="L4", volumes={"/cache": cache}, scaledown_window=180, timeout=900,
         secrets=[modal.Secret.from_name("replyflow-voxcpm")])
@modal.concurrent(max_inputs=4)
class Voice:
    @modal.enter()
    def load(self):
        import voxcpm_server
        self.model = voxcpm_server.load_model()
        cache.commit()

    @modal.asgi_app()
    def web(self):
        import os
        import voxcpm_server
        return voxcpm_server.create_app(self.model, os.environ.get("VOXCPM_API_KEY", ""))
