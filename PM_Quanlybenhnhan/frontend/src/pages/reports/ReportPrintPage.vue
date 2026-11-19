<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import PageHeader from '@/components/common/PageHeader.vue'
import { companiesService } from '@/services/companies'
import { examsService } from '@/services/exams'
import { patientsService } from '@/services/patients'
import type { Company, Paginated, Patient } from '@/types'
import { keyword, prepareWord, printWordBatch } from '@/utils/printDocx'

const companies = ref<Company[]>([])
const companyId = ref('')
const examDate = ref('')
const people = ref<Patient[]>([])
const selected = ref<string[]>([])
const search = ref('')
const error = ref('')
const loading = ref(false)
const printing = ref(false)
const template = shallowRef<Awaited<ReturnType<typeof prepareWord>>>()
const constants = ref<Record<string, string>>({})
const mapping = ref<Record<string, string>>({})
const busy = computed(() => loading.value || printing.value)
const visible = computed(() => {
  const query = keyword(search.value)
  return people.value.filter((person) =>
    [person.full_name, person.employee_code ?? ''].some((value) => keyword(value).includes(query)),
  )
})
const displayDate = (value: string | null) => value?.split('-').reverse().join('/') ?? ''

async function allPages<T>(fetch: (page: number) => Promise<{ data: Paginated<T> }>) {
  const rows: T[] = []
  for (let page = 1; ; page++) {
    const { data } = await fetch(page)
    rows.push(...data.results)
    if (!data.next) return rows
  }
}

async function loadPeople() {
  selected.value = []
  people.value = []
  if (!companyId.value) return
  loading.value = true
  error.value = ''
  try {
    const company = companyId.value
    const day = examDate.value
    const [patients, exams] = await Promise.all([
      allPages((page) => patientsService.list({ company, is_active: true, page, page_size: 100 })),
      day
        ? allPages((page) =>
            examsService.list({ company, date_from: day, date_to: day, page, page_size: 100 }),
          )
        : [],
    ])
    const patientIds = new Set(exams.map((exam) => exam.patient))
    people.value = patients.filter((patient) => !day || patientIds.has(patient.id))
  } catch {
    error.value = 'Không tải được danh sách nhân viên.'
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  loading.value = true
  try {
    companies.value = await allPages((page) => companiesService.list({ page, page_size: 100 }))
  } catch {
    error.value = 'Không tải được danh sách công ty.'
  } finally {
    loading.value = false
  }
})
watch([companyId, examDate], loadPeople)

function values(person: Patient, index: number): Record<string, string> {
  const company = companies.value.find((item) => item.id === companyId.value)?.name ?? ''
  const gender = { M: 'Nam', F: 'Nữ' }[person.gender] ?? ''
  return {
    so: String(index + 1),
    stt: String(index + 1),
    hovaten: person.full_name,
    hoten: person.full_name,
    manv: person.employee_code ?? '',
    manhanvien: person.employee_code ?? '',
    gt: gender,
    gioitinh: gender,
    ngaysinh: displayDate(person.dob),
    sinhngay: displayDate(person.dob),
    cccd: person.cccd,
    ngaycap: displayDate(person.cccd_issued_date),
    ngaycapcccd: displayDate(person.cccd_issued_date),
    noicap: person.cccd_issued_place,
    noicapcccd: person.cccd_issued_place,
    noiohientai: person.address,
    diachihientai: person.address,
    sdt: person.phone,
    bophan: person.department,
    noicongtac: company,
    congty: company,
    noicongtachoctap: company,
    ngaykham: displayDate(examDate.value),
  }
}
const sampleFields = computed(() => (people.value[0] ? values(people.value[0], 0) : {}))
const unmapped = computed(
  () =>
    template.value?.names.filter((name) => !Object.hasOwn(sampleFields.value, keyword(name))) ?? [],
)

async function loadTemplate(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  template.value = undefined
  constants.value = {}
  mapping.value = {}
  if (!file) return
  loading.value = true
  error.value = ''
  try {
    template.value = await prepareWord(file)
  } catch {
    error.value = 'Không đọc được mẫu Word. Hãy chọn tệp .docx hợp lệ.'
  } finally {
    loading.value = false
  }
}

async function print(list: Patient[]) {
  if (!template.value || !list.length || busy.value) return
  printing.value = true
  error.value = ''
  try {
    const common = Object.fromEntries(
      Object.entries(constants.value).map(([name, value]) => [keyword(name), value]),
    )
    await printWordBatch(
      template.value,
      list.map((person, index) => {
        const fields = values(person, index)
        const mapped = Object.fromEntries(
          Object.entries(mapping.value)
            .filter(([, field]) => field)
            .map(([name, field]) => [keyword(name), fields[field] ?? '']),
        )
        return { ...common, ...fields, ...mapped }
      }),
    )
  } catch {
    error.value = 'Không tạo được bản in từ mẫu Word đã chọn.'
  } finally {
    printing.value = false
  }
}
</script>

<template>
  <PageHeader title="In Báo Cáo" />
  <section class="rounded bg-white p-4">
    <div class="flex flex-wrap items-end gap-4">
      <label class="grid gap-1">
        Công ty
        <select v-model="companyId" class="rounded border p-2" :disabled="busy">
          <option value="">Chọn công ty</option>
          <option v-for="company in companies" :key="company.id" :value="company.id">
            {{ company.name }}
          </option>
        </select>
      </label>
      <label class="grid gap-1">
        Ngày khám
        <input v-model="examDate" type="date" class="rounded border p-2" :disabled="busy" />
      </label>
      <label class="grid gap-1">
        Mẫu Word
        <input type="file" accept=".docx" :disabled="busy" @change="loadTemplate" />
      </label>
    </div>
    <p v-if="error" role="alert" class="mt-3 text-red-700">{{ error }}</p>
    <p v-if="busy" role="status" class="mt-3">
      {{ printing ? 'Đang chuẩn bị bản in…' : 'Đang tải…' }}
    </p>
    <details v-if="unmapped.length && people.length" class="mt-4">
      <summary>Liên kết keyword bổ sung</summary>
      <div class="mt-2 grid gap-2 sm:grid-cols-2">
        <label v-for="name in unmapped" :key="name" class="grid gap-1">
          {{ name }}
          <select v-model="mapping[name]" class="rounded border p-2" :disabled="busy">
            <option value="">Giá trị chung hoặc để trống</option>
            <option v-for="(_, field) in sampleFields" :key="field" :value="field">
              {{ field }}
            </option>
          </select>
          <input
            v-if="!mapping[name]"
            v-model="constants[name]"
            class="rounded border p-2"
            :disabled="busy"
            placeholder="Giá trị chung"
          />
        </label>
      </div>
    </details>
    <div v-if="companyId" class="mt-5">
      <div class="flex flex-wrap items-center gap-3">
        <input
          v-model="search"
          placeholder="Tìm họ tên hoặc mã nhân viên"
          aria-label="Tìm nhân viên"
          class="rounded border p-2"
        />
        <button
          type="button"
          class="rounded border px-3 py-2"
          :disabled="busy || !visible.length"
          @click="selected = [...new Set([...selected, ...visible.map((person) => person.id)])]"
        >
          Chọn tất cả kết quả
        </button>
        <button
          type="button"
          class="rounded border px-3 py-2"
          :disabled="busy || !selected.length"
          @click="selected = []"
        >
          Bỏ chọn
        </button>
        <button
          type="button"
          class="rounded bg-teal-700 px-3 py-2 text-white disabled:opacity-50"
          :disabled="busy || !template || !selected.length"
          @click="print(people.filter((person) => selected.includes(person.id)))"
        >
          In đã chọn ({{ selected.length }})
        </button>
      </div>
      <table class="mt-3 w-full text-left">
        <thead>
          <tr class="border-b">
            <th>Chọn</th>
            <th>Mã nhân viên</th>
            <th>Họ và tên</th>
            <th>Thao tác</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="person in visible" :key="person.id" class="border-b">
            <td>
              <input
                v-model="selected"
                type="checkbox"
                :value="person.id"
                :aria-label="'Chọn ' + person.full_name"
                :disabled="busy"
              />
            </td>
            <td>{{ person.employee_code }}</td>
            <td class="py-2">{{ person.full_name }}</td>
            <td>
              <button
                type="button"
                class="text-teal-700 disabled:opacity-50"
                :disabled="busy || !template"
                @click="print([person])"
              >
                In lẻ
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="!visible.length && !busy" class="mt-3">Không có nhân viên phù hợp.</p>
    </div>
  </section>
</template>
