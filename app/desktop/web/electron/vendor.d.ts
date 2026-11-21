declare module 'json-dup-key-validator' {
  const validator: { parse(text: string, allowDuplicatedKeys: boolean): unknown }
  export default validator
}
