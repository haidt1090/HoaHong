import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { diagnosisService } from '@/services/diagnosis'
import type { DiagnosisKeyword, DiagnosisKeywordInput } from '@/types'

interface KeywordFilters {
  search: string
  classification: number | null
  page: number
  page_size: number
}

export const useDiagnosisStore = defineStore('diagnosis', () => {
  // Keyword state
  const keywords = ref<DiagnosisKeyword[]>([])
  const keywordTotal = ref(0)
  const keywordsLoading = ref(false)

  const keywordFilters = reactive<KeywordFilters>({
    search: '',
    classification: null,
    page: 1,
    page_size: 100,
  })

  // Keyword actions
  async function fetchKeywords(): Promise<void> {
    keywordsLoading.value = true
    try {
      const { data } = await diagnosisService.listKeywords({
        search: keywordFilters.search || undefined,
        classification: keywordFilters.classification ?? undefined,
        page: keywordFilters.page,
        page_size: keywordFilters.page_size,
      })
      keywords.value = data.results ?? []
      keywordTotal.value = data.count ?? 0
    } finally {
      keywordsLoading.value = false
    }
  }

  async function createKeyword(payload: DiagnosisKeywordInput): Promise<DiagnosisKeyword> {
    const { data } = await diagnosisService.createKeyword(payload)
    await fetchKeywords()
    return data
  }

  async function updateKeyword(id: string, payload: Partial<DiagnosisKeywordInput>): Promise<DiagnosisKeyword> {
    const { data } = await diagnosisService.updateKeyword(id, payload)
    await fetchKeywords()
    return data
  }

  async function removeKeyword(id: string): Promise<void> {
    await diagnosisService.removeKeyword(id)
    keywords.value = keywords.value.filter((k) => k.id !== id)
    keywordTotal.value -= 1
  }

  async function importKeywords(file: File, mode: 'append' | 'replace' = 'append') {
    const { data } = await diagnosisService.importKeywords(file, mode)
    await fetchKeywords()
    return data
  }

  function resetKeywordFilters(): void {
    keywordFilters.search = ''
    keywordFilters.classification = null
    keywordFilters.page = 1
  }

  return {
    keywords,
    keywordTotal,
    keywordsLoading,
    keywordFilters,
    fetchKeywords,
    createKeyword,
    updateKeyword,
    removeKeyword,
    importKeywords,
    resetKeywordFilters,
  }
})
