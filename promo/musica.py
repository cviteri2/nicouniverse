"""Música original para los videos (sintetizada, sin voz ni muestras de terceros).
Uso: python3 musica.py <variante 1|2|3> <segundos> <salida.wav>
La batería entra a los 6 s, justo cuando termina la barra de búsqueda."""
import sys, wave
import numpy as np

SR = 44100
v, dur, out = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
BPM = 120.0
beat = 60 / BPM
n = int(SR * dur)
L = np.zeros(n); R = np.zeros(n)
rng = np.random.default_rng(v)

def midi(m): return 440 * 2 ** ((m - 69) / 12)

def add(sig, t0, pan=0.0, gain=1.0):
    i = int(t0 * SR)
    if i >= n: return
    s = sig[: n - i] * gain
    L[i:i + len(s)] += s * (1 - pan) / 2 * 2 ** .5
    R[i:i + len(s)] += s * (1 + pan) / 2 * 2 ** .5

def env(length, a, d_tau):
    t = np.arange(int(length * SR)) / SR
    return np.minimum(1, t / a) * np.exp(-t / d_tau), t

def pluck(f, length=.6, tau=.18):
    e, t = env(length, .004, tau)
    return e * (np.sin(2*np.pi*f*t) + .35*np.sin(4*np.pi*f*t) + .12*np.sin(6*np.pi*f*t))

def pad(fs, length):
    t = np.arange(int(length * SR)) / SR
    e = np.minimum(1, t / .6) * np.minimum(1, (length - t) / .6)
    s = sum(np.sin(2*np.pi*f*d*t + p) for f in fs for d, p in ((1, 0), (1.004, 1), (.996, 2)))
    return e * s / (3 * len(fs))

def bass(f, length):
    e, t = env(length, .01, length * .7)
    return e * (np.sin(2*np.pi*f*t) + .25*np.sin(4*np.pi*f*t))

def kick():
    t = np.arange(int(.35 * SR)) / SR
    f = 50 + 90 * np.exp(-t / .04)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t / .12)

def hat():
    x = rng.standard_normal(int(.06 * SR)); x = np.diff(x, prepend=0)
    return x * np.exp(-np.arange(len(x)) / SR / .015) * .25

def clap():
    x = rng.standard_normal(int(.2 * SR)); x = np.diff(x, prepend=0)
    return x * np.exp(-np.arange(len(x)) / SR / .05) * .35

# Progresiones (raíces MIDI) y patrón de arpegio por variante.
PROG = {1: [60, 67, 69, 65], 2: [62, 69, 71, 67], 3: [57, 65, 60, 67]}[v]   # C G Am F · D A Bm G · Am F C G
MINOR = {1: [False, False, True, False], 2: [False, False, True, False], 3: [True, False, False, False]}[v]
ARP = {1: [0, 2, 1, 2, 3, 2, 1, 2], 2: [0, 1, 2, 3, 2, 1, 2, 3], 3: [0, 2, 3, 1, 2, 3, 1, 2]}[v]
DRUMS_AT = 6.0
bar = 4 * beat
nbars = int(np.ceil(dur / bar))
for b in range(nbars):
    t0 = b * bar
    root = PROG[b % 4]
    third = 3 if MINOR[b % 4] else 4
    chord = [root, root + third, root + 7, root + 12]
    add(pad([midi(m - 12) for m in chord[:3]], bar + .3), t0, 0, .22)
    for k in range(8):
        m = chord[ARP[k]] + (12 if v == 2 and k % 4 == 3 else 0)
        add(pluck(midi(m)), t0 + k * beat / 2, -.3 if k % 2 else .3, .16 if t0 < DRUMS_AT else .2)
    if t0 >= DRUMS_AT - 1e-6:
        for k in range(4):
            add(kick(), t0 + k * beat, 0, .55)
            add(hat(), t0 + k * beat + beat / 2, .4, .5)
            if v != 3: add(hat(), t0 + k * beat + beat / 4 * 3, -.3, .25)
        for k in (1, 3): add(clap(), t0 + k * beat, 0, .5)
        for k in range(4):
            add(bass(midi(root - 24 + (7 if v == 2 and k == 3 else 0)), beat * .9), t0 + k * beat, 0, .35)
    else:
        add(bass(midi(root - 24), bar), t0, 0, .18)

# Eco sencillo (corchea con puntillo) para dar espacio.
d = int(beat * .75 * SR)
for ch in (L, R):
    ch[d:] += ch[:-d] * .22
# Barrido ascendente hacia la entrada de la batería.
t = np.arange(int(1.0 * SR)) / SR
sweep = rng.standard_normal(len(t)); sweep = np.convolve(sweep, np.ones(6) / 6, 'same') * (t / 1.0) ** 2 * .12
add(sweep, DRUMS_AT - 1.0, 0)

mix = np.stack([L, R], 1)
fade_in = np.minimum(1, np.arange(n) / (SR * .3))
fade_out = np.minimum(1, (n - np.arange(n)) / (SR * 1.8))
mix *= (fade_in * fade_out)[:, None]
mix = np.tanh(mix * 1.1)
mix /= np.abs(mix).max() / .89
with wave.open(out, 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((mix * 32767).astype('<i2').tobytes())
