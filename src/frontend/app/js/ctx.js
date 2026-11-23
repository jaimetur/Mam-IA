// What every screen needs to know: who is signed in, their family and its subscription, and their member id.
export const ctx = {
  me: null,          // the account (/api/me → user)
  family: null,      // the family (name, accounts, invites…)
  billing: null,     // the subscription's state
  myMember: null,    // the member document of the person using the app
  native: typeof window !== "undefined" ? window.MamIANative || null : null,   // the Android app's bridge
};

export function setMe(r) {
  ctx.me = r.user;
  ctx.family = r.family;
  ctx.billing = r.billing;
  ctx.myMember = r.user.memberId;
}
