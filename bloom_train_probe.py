#!/usr/bin/env python3
import torch
import torch.nn as nn
import torch.optim as optim

def run_probe():
    model = nn.Linear(256, 256)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    x = torch.randn(2, 256)
    target = torch.randn(2, 256)
    optimizer.zero_grad()
    out = model(x)
    loss = nn.functional.mse_loss(out, target)
    loss.backward()
    optimizer.step()
    return loss.item()

if __name__ == "__main__":
    run_probe()
