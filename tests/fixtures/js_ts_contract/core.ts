export function inc(value: number): number {
  return value + 1;
}
export function entry(value: number): number {
  return inc(value);
}
export function overloaded(value: string): string;
export function overloaded(value: number): number;
export function overloaded(value: string | number): string | number {
  return value;
}
export class Counter {
  next(value: number): number { return inc(value); }
}
