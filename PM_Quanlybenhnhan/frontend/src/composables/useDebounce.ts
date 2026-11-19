import { ref, watch, type Ref } from 'vue'

/** Returns a debounced copy of the given ref that updates after `delay` ms. */
export function useDebounce<T>(value: Ref<T>, delay = 300): Ref<T> {
  const debounced = ref<T>(value.value) as Ref<T>
  let timer: ReturnType<typeof setTimeout> | undefined

  watch(value, (newVal) => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      debounced.value = newVal
    }, delay)
  })

  return debounced
}
