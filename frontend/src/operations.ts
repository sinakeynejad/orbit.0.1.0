/** Cancels superseded work and prevents stale async results from updating the UI. */
export class LatestOperation {
 private controller: AbortController | null = null;
 begin() {
  this.cancel();
  const controller = new AbortController();
  this.controller = controller;
  return {signal: controller.signal, isCurrent: () => this.controller === controller && !controller.signal.aborted};
 }
 cancel() { this.controller?.abort(); this.controller = null; }
}
