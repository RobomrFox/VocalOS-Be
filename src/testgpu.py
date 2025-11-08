import torch

print(f"CUDA available: {torch.cuda.is_available()}")
print(f"Mac Metal GPU available: {torch.backends.mps.is_available()}")
