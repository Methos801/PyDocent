"use strict";
let worker;
let generation = 0;
let timer;
let active;
function finish(result) {
  clearTimeout(timer);
  worker?.terminate();
  worker = null;
  const session = active;
  active = null;
  if (session) parent.postMessage({ id: session.id, result }, session.origin);
}
addEventListener("message", ({source, origin, data}) => {
  if (source !== parent || !/^http:\/\/127\.0\.0\.1:\d+$/.test(origin) || !data) return;
  if (data.stop && active?.id === data.id && active.origin === origin) {
    finish({error: "You stopped the program."});
    return;
  }
  if (active || typeof data.id !== "string" || data.id.length !== 32 ||
      typeof data.code !== "string" || data.code.length > 100000 ||
      typeof data.stdin !== "string" || data.stdin.length > 10000) return;
  active = {id: data.id, origin};
  const run = ++generation;
  let started = false;
  try {
    worker = new Worker("/worker.js", {type: "module"});
    timer = setTimeout(() => finish({error: "Python could not start. Try again."}), 30000);
    worker.onmessage = ({data: message}) => {
      if (generation !== run || !active || !message) return;
      if (message.ready === true) {
        if (started) return;
        started = true;
        clearTimeout(timer);
        timer = setTimeout(() => finish({error: "Your program took too long and was stopped."}), 5000);
        worker.postMessage({code: data.code, stdin: data.stdin, check: data.check});
        return;
      }
      finish(message.result);
    };
    worker.onerror = () => finish({error: "Python stopped unexpectedly. Try again."});
  } catch {
    finish({error: "The browser could not start Python."});
  }
});
