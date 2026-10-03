export function add(a, b) {
  return a + b;
}
export const twice = value => add(value, value);
export class Box {
  get() { return this.value; }
}
export default function main() {
  return twice(2);
}
