export async function collectCompleteScreeningState(fetchPage, pageLimit = 500) {
  const results = [];
  const identities = new Set();
  let authoritativeTotal = null;
  let snapshotIdentity = null;
  let scope = null;
  let retainedNonactiveTotal = null;
  let apiVersion = null;

  while (authoritativeTotal === null || results.length < authoritativeTotal) {
    const requestedOffset = results.length;
    const response = await fetchPage(pageLimit, requestedOffset);
    const page = response.data;
    if (page.offset !== requestedOffset || page.limit !== pageLimit) {
      throw new Error("Screening pagination contract mismatch");
    }
    if (authoritativeTotal === null) {
      authoritativeTotal = page.total;
      snapshotIdentity = page.snapshot_identity;
      scope = page.scope;
      retainedNonactiveTotal = page.retained_nonactive_total;
      apiVersion = response.apiVersion;
    } else if (
      page.total !== authoritativeTotal ||
      page.snapshot_identity !== snapshotIdentity ||
      page.scope !== scope ||
      page.retained_nonactive_total !== retainedNonactiveTotal
    ) {
      throw new Error("Screening state changed during pagination; retry required");
    }
    if (!page.results.length && results.length < authoritativeTotal) {
      throw new Error("Screening pagination ended before authoritative total");
    }
    for (const item of page.results) {
      const identity = `${item.signal_id}:${item.symbol}`;
      if (identities.has(identity)) {
        throw new Error(`Duplicate screening identity across pages: ${identity}`);
      }
      identities.add(identity);
      results.push(item);
    }
  }
  if (results.length !== authoritativeTotal) {
    throw new Error("Screening page union exceeds authoritative total");
  }
  return {
    data: {
      results,
      total: authoritativeTotal,
      limit: pageLimit,
      offset: 0,
      snapshot_identity: snapshotIdentity,
      scope,
      retained_nonactive_total: retainedNonactiveTotal,
    },
    apiVersion,
  };
}
