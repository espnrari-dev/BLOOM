import subprocess, json
for i in range(10):
    subprocess.run(["python3","frontier.py"])
    seed=json.load(open("garden/seedling.json"))
    print(f"After run {i+5}: gen {seed['gen']} wind mean {seed['petals']['wind']['mean']:.3f} dew {json.load(open('garden/dew.json'))['dew']:.1f}")
