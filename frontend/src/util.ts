export function groupBy<T, K extends keyof T & string>(
  array: T[],
  key: K | ((obj: T) => string)
) {
  // Return the end result
  return array.reduce((result, currentValue) => {
    let item;
    if (typeof key === "string") {
      item = currentValue[key];
    } else {
      item = key(currentValue);
    }
    if (typeof item === "string") {
      // If an array already present for key, push it to the array. Else create an array and push the object
      (result[item] = result[item] || []).push(currentValue);
    }
    // Return the current iteration `result` value, this will be taken as next iteration `result` value and accumulate
    return result;
  }, {} as { [key: string]: T[] }); // empty object is the initial value for result object
}
