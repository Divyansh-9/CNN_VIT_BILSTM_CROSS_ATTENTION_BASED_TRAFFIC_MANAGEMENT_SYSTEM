export function simulatedPhase(traffic, elapsed) {
  const greenByApproach = traffic.windows[0]?.green;
  if (!greenByApproach) return null;
  const groups = [["N", "S"], ["E", "W"]]
    .map(group => group.filter(a => a in greenByApproach)).filter(group => group.length);
  if (!groups.length) return null;
  let start = 0, index = 0, latest = -1;
  for (;;) {
    // Only a finished demand window may change the next green.
    while (traffic.windows[latest + 1]?.t + 30 <= start && traffic.windows[latest + 1]?.end <= start) latest += 1;
    const group = groups[index % groups.length];
    const green = latest < 0 ? traffic.policy.previous_green : Math.max(...group.map(a => traffic.windows[latest].green[a]));
    for (const [label, seconds] of [[`${group.join(" / ")} green`, green],
      ["Yellow clearance", traffic.policy.yellow], ["All red clearance", traffic.policy.all_red]]) {
      if (elapsed < start + seconds) return { label, remaining: Math.ceil(start + seconds - elapsed) };
      start += seconds;
    }
    index += 1;
  }
}
