// The film's 3D shots: for film time t, the pose of the Flipper, the stickers, the camera and the screen.
// Units are the Flipper model's (1.0 = 100 mm; the device is centred, its screen faces +Z, its back is at z = -0.13).
// Times come from window.TM (sound/mix.py), window.TAPE (stage/tape.py: the real screen, presses, note onsets) and
// window.VO (the narration's word times). stage/render.py renders each shot's frames; nothing here is random.
(function () {
  const TM = window.TM, TAPE = window.TAPE, C = TM.cues;
  const PINK = "radial-gradient(120% 95% at 50% 42%, #ffc2df 0%, #ff9acb 62%, #f986bd 100%)";

  // ---- helpers
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const io = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);   // cubic in-out
  const oc = (x) => 1 - Math.pow(1 - x, 3);                                         // cubic out
  const mix = (a, b, k) => (Array.isArray(a) ? a.map((v, i) => v + (b[i] - v) * k) : a + (b - a) * k);
  // keyframes [[t, value], ...] -> eased value at t (holds before the first and after the last key)
  const key = (t, ks, ease = io) => {
    if (t <= ks[0][0]) return ks[0][1];
    for (let i = 1; i < ks.length; i++) if (t <= ks[i][0]) {
      const [t0, a] = ks[i - 1], [t1, b] = ks[i];
      return mix(a, b, ease((t - t0) / (t1 - t0)));
    }
    return ks[ks.length - 1][1];
  };
  const bez = (a, c, b, k) => a.map((v, i) => (1 - k) * (1 - k) * v + 2 * (1 - k) * k * c[i] + k * k * b[i]);
  // the screen at t: the last tape step at or before t
  const screenAt = (steps, t) => { let s = steps[0][1]; for (const [ts, id] of steps) if (ts <= t + 1e-6) s = id; return s; };
  // buttons: a press dips/tilts over 0.07 s and comes back over 0.16 s
  const buttons = (presses, t) => {
    const b = { dpad: 0, tiltX: 0, tiltY: 0, back: 0 };
    for (const [tp, k] of presses) {
      const d = t - tp; if (d < 0 || d > 0.24) continue;
      const e = d < 0.07 ? oc(d / 0.07) : 1 - io((d - 0.07) / 0.17);
      if (k === "OK") b.dpad += 0.0055 * e;
      if (k === "BACK") b.back += 0.0055 * e;
      if (k === "UP") b.tiltX -= 0.075 * e;
      if (k === "DOWN") b.tiltX += 0.075 * e;
      if (k === "LEFT") b.tiltY -= 0.075 * e;
      if (k === "RIGHT") b.tiltY += 0.075 * e;
    }
    return b;
  };
  // orbit the camera around a target: azimuth (0 = straight in front, + = to the right), elevation, radius
  const orbit = (target, az, el, r) => [target[0] + r * Math.sin(az) * Math.cos(el), target[1] + r * Math.sin(el), target[2] + r * Math.cos(az) * Math.cos(el)];
  const DOCK = [0.05, 0.0, -0.1345];          // a sticker held flat on the back (flipper-local), facing -Z
  const FACE_BACK = [0, Math.PI, 0];

  // ---------------------------------------------------------------- s1 hook: the sticker alone
  function s1(t) {
    const t0 = TM.s1[0];
    const u = t - t0;
    // edge-on to nearly face-on by the time "504" lands, then a slow turn
    const ry = key(t, [[t0, 1.25], [C.h_count - 0.1, 0.52]]) - 0.03 * Math.max(0, t - C.h_count);
    const rx = key(t, [[t0, -0.10], [C.h_count - 0.1, -0.55]]);
    return {
      bg: PINK, shadow: 0.13, floorY: -0.24,
      cam: { pos: key(t, [[t0, [0.06, 0.07, 0.70]], [TM.s1[1], [0.0, 0.13, 0.86]]], (x) => x), target: [0.0, 0.0, 0], fov: 30 },
      flipper: { visible: false },
      sticker: { visible: true, pos: [-0.17, 0.012 * Math.sin(u * 0.9), 0], rot: [rx, ry, 0.10] },
    };
  }

  // ---------------------------------------------------------------- s3 burn
  function s3(t) {
    const B = TAPE.burn;
    const t0 = TM.s3[0], dock = C.burn_dock, orb = C.burn_orbit;
    // the camera: a slow push on the front three-quarter view, then round to the back (1.5 s), then a drift
    const target = key(t, [[t0, [-0.04, 0.0, 0.0]], [orb, [-0.03, 0.0, 0.0]], [orb + 1.5, [0.03, 0.0, -0.06]]]);
    const az = key(t, [[t0, 0.30], [orb, 0.24], [orb + 1.5, 2.55], [TM.s3[1], 2.62]]);
    const el = key(t, [[t0, 0.15], [orb, 0.12], [orb + 1.5, 0.16]]);
    const r = key(t, [[t0, 1.62], [C.burn_fly, 1.30], [orb, 1.26], [orb + 1.5, 1.05], [TM.s3[1], 0.98]]);
    // the sticker: flies in from the upper right, round the right end, onto the back (flipper-local path)
    let st = { visible: false };
    if (t >= C.burn_fly) {
      const k = clamp((t - C.burn_fly) / (dock - C.burn_fly));
      const e = io(k);
      st = { visible: true, parent: "flipper", pos: t >= dock ? DOCK : bez([0.95, 0.42, 0.55], [0.86, 0.12, -0.42], DOCK, e),
             rot: mix([-0.5, 0.35, 0.2], FACE_BACK, oc(k)) };
    }
    const pulse = t >= dock && t < dock + 1.1 ? (t - dock) / 1.1 : null;
    // round the back: more fill, and a ring drawn round the sticker once the camera has arrived
    const hk = clamp((t - orb - 1.25) / 0.45);
    const halo = hk > 0 ? { pos: [DOCK[0], DOCK[1], DOCK[2] - 0.006], opacity: 0.95 * oc(hk), scale: 1.25 - 0.25 * oc(hk) } : null;
    return {
      bg: PINK, shadow: 0.15, floorY: -0.40, fill: key(t, [[orb, 0.55], [orb + 1.5, 1.05]]),
      cam: { pos: orbit(target, az, el, r), target, fov: 30 },
      flipper: { rot: [0, 0, 0] }, buttons: buttons(B.presses, t),
      sticker: st, pulse, halo, screen: screenAt(B.steps, t),
    };
  }

  // ---------------------------------------------------------------- s5 play: tap, then the tune
  function s5(t) {
    const P = TAPE.play;
    const t0 = TM.s5[0];
    const target = key(t, [[t0, [-0.02, 0.0, 0.0]], [TM.solo, [-0.04, 0.01, 0.02]], [TM.return, [-0.066, 0.035, 0.08]]]);
    const az = key(t, [[t0, -0.36], [TM.solo, -0.30], [TM.return, -0.16]]);
    const el = key(t, [[t0, 0.13], [TM.return, 0.08]]);
    const r = key(t, [[t0, 1.50], [C.play_fly, 1.30], [TM.solo, 1.24], [TM.return, 0.74]], (x) => io(x));
    // the tap: in round the pointed (left) end, touch the back, away again
    let st = { visible: false };
    if (t >= C.play_fly && t < C.play_away + 0.9) {
      const kin = clamp((t - C.play_fly) / (C.play_contact - C.play_fly));
      const kout = clamp((t - C.play_away) / 0.9);
      const pos = t < C.play_contact ? bez([-1.0, 0.45, 0.6], [-0.92, 0.10, -0.42], DOCK, io(kin))
                : t < C.play_away ? DOCK : bez(DOCK, [-0.85, 0.08, -0.45], [-1.1, 0.5, 0.2], io(kout));
      st = { visible: true, parent: "flipper", pos, rot: t < C.play_contact ? mix([-0.5, -0.4, -0.2], FACE_BACK, oc(kin)) : FACE_BACK };
    }
    const pulse = t >= C.play_contact && t < C.play_contact + 1.1 ? (t - C.play_contact) / 1.1 : null;
    // the LED blinks cyan on every note (nfc_cart.c: sequence_blink_cyan_10), held two frames so it reads
    let led = 0;
    for (const tn of P.notes) { const d = t - tn; if (d >= 0 && d < 0.14) led = Math.max(led, 3.2 * (1 - d / 0.14)); }
    return {
      bg: PINK, shadow: 0.15, floorY: -0.40,
      cam: { pos: orbit(target, az, el, r), target, fov: 30 },
      flipper: { rot: [0, 0, 0] }, buttons: buttons(P.presses, t), led, ledColor: "#00e5ff",
      sticker: st, pulse, screen: screenAt(P.steps, t),
    };
  }

  // ---------------------------------------------------------------- s6 proof: three stickers
  const ROW = [-0.42, 0, 0.42];
  function s6(t) {
    const ts = [C.p_213, C.p_215, C.p_216];
    const sts = ROW.map((x, i) => {
      const k = clamp((t - ts[i] + 0.12) / 0.55);
      const s = k <= 0 ? 0 : 1 + 0.08 * Math.sin(Math.PI * k) * (1 - k) + (oc(k) - 1);
      const d = Math.max(0, t - ts[i]);
      return { visible: k > 0, pos: [x, 0.10 + 0.008 * Math.sin(d * 1.1 + i), 0], scale: Math.max(0.001, s),
               rot: [-0.55 + 0.05 * Math.sin(d * 0.7 + i), 0.45 + 0.6 * (1 - oc(k)) + 0.07 * Math.sin(d * 0.55 + 2 * i), 0.1] };
    });
    return {
      bg: PINK, shadow: 0.12, floorY: -0.20,
      cam: { pos: [0, 0.10 + 0.02 * clamp((t - TM.s6[0]) / 10), 1.5], target: [0, 0.10, 0], fov: 30 },
      flipper: { visible: false }, stickers: sts,
    };
  }

  // ---------------------------------------------------------------- s7 end card: the Flipper and a cartridge, turning
  function s7(t) {
    const u = t - TM.s7[0];
    const k = oc(clamp(u / 1.2));
    return {
      bg: "#ff9acb", shadow: 0.13, floorY: -0.42,
      cam: { pos: [0, 0.06, 2.8], target: [0, 0.0, 0], fov: 30 },
      flipper: { pos: [0.58, -0.04 + 0.04 * (1 - k), 0], rot: [-0.08, -0.40 + 0.02 * u + 0.25 * (1 - k), 0], scale: 1.12 },
      sticker: { visible: true, pos: [0.96, 0.31 + 0.012 * Math.sin(u * 0.9), 0.2], rot: [-0.55, 0.5 - 0.03 * u, 0.1], scale: 1.12 * k + 0.001 },
      screen: "s0017",
    };
  }

  const SHOTS = { s1, s3, s5, s6, s7 };
  // which 3D shot holds film time t (later shots win where windows overlap: each starts on its bar line)
  window.SHOT_POSE = (t) => {
    let pick = null;
    for (const s of TM.shots3d) if (t >= TM[s][0] - 1e-6 && t < TM[s][1] + 1e-6) pick = s;
    const p = pick ? SHOTS[pick](t) : { bg: "#ff9acb", cam: { pos: [0, 0, 3], target: [0, 0, 0] }, flipper: { visible: false } };
    p.shot = pick;
    return p;
  };
  window.SHOT_FNS = SHOTS;
})();
