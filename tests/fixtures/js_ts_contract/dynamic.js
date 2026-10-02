export function entry(obj) {
  return obj.run();
}
export function later(name) {
  return import(name);
}
