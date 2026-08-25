#!/usr/bin/env python3
import torch
import torch.nn as nn
import torch.optim as optim

def run_real_training_probe():
    model = nn.Sequential(
        nn.Linear(256, 512),
        nn.ReLU(),
        nn.Linear(512, 256)
    )
    optimizer = optim.AdamW(model.parameters(), lr=1e-4)
    x = torch.randn(4, 256)
    target = torch.randn(4, 256)
    
    optimizer.zero_grad()
    output = model(x)
    loss = nn.functional.mse_loss(output, target)
    loss.backward()
    optimizer.step()
    return loss.item()

if __name__ == "__main__":
    run_real_training_probe()
