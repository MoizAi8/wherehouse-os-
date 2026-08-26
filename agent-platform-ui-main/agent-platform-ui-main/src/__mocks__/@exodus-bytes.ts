export interface BytesLike {
  readonly byteLength: number
  readonly [Symbol.toStringTag]: "Uint8Array"
  [index: number]: number
}

export function fromHex(hex: string): Uint8Array {
  if (!hex || hex.length === 0) return new Uint8Array(0)
  const cleanHex = hex.startsWith("0x") ? hex.slice(2) : hex
  const len = cleanHex.length / 2
  const bytes = new Uint8Array(len)
  for (let i = 0; i < len; i++) {
    bytes[i] = parseInt(cleanHex.substring(i * 2, i * 2 + 2), 16)
  }
  return bytes
}

export function toHex(bytes: BytesLike): string {
  return Array.from(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
}

export function toBase64(bytes: BytesLike): string {
  if (typeof btoa !== "undefined") {
    return btoa(String.fromCharCode(...new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength)))
  }
  return Buffer.from(bytes).toString("base64")
}

export function fromBase64(str: string): Uint8Array {
  if (typeof atob !== "undefined") {
    const binary = atob(str)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  }
  return Buffer.from(str, "base64")
}

export function concat(...arrays: BytesLike[]): Uint8Array {
  const totalLength = arrays.reduce((sum, arr) => sum + arr.byteLength, 0)
  const result = new Uint8Array(totalLength)
  let offset = 0
  for (const arr of arrays) {
    result.set(new Uint8Array(arr.buffer, arr.byteOffset, arr.byteLength), offset)
    offset += arr.byteLength
  }
  return result
}

export function equals(a: BytesLike, b: BytesLike): boolean {
  if (a.byteLength !== b.byteLength) return false
  const aBytes = new Uint8Array(a.buffer, a.byteOffset, a.byteLength)
  const bBytes = new Uint8Array(b.buffer, b.byteOffset, b.byteLength)
  for (let i = 0; i < aBytes.length; i++) {
    if (aBytes[i] !== bBytes[i]) return false
  }
  return true
}

export function randomBytes(length: number): Uint8Array {
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    const arr = new Uint8Array(length)
    crypto.getRandomValues(arr)
    return arr
  }
  const arr = new Uint8Array(length)
  for (let i = 0; i < length; i++) {
    arr[i] = Math.floor(Math.random() * 256)
  }
  return arr
}

export const Bytes = {
  fromHex,
  toHex,
  toBase64,
  fromBase64,
  concat,
  equals,
  randomBytes
}

export default Bytes