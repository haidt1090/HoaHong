<template>
  <div class="flex flex-col gap-4">
    <div class="grid grid-cols-1 gap-4 md:grid-cols-2">
      <FormField label="Tài khoản liên thông" required>
        <InputText
          :model-value="modelValue.username"
          placeholder="vd: 8934285091236_api"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('username', v ?? '')"
        />
      </FormField>

      <FormField label="Mật khẩu" :required="!config?.password_set">
        <Password
          :model-value="modelValue.password"
          :feedback="false"
          toggle-mask
          placeholder="Bỏ trống để giữ nguyên"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('password', v ?? '')"
        />
      </FormField>

      <FormField label="Mã CSKCB (sender_id / GTIN)" required>
        <InputText
          :model-value="modelValue.sender_id"
          placeholder="vd: 8934285091236"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('sender_id', v ?? '')"
        />
      </FormField>

      <FormField label="MA_CSKCB (facility_code)">
        <InputText
          :model-value="modelValue.facility_code"
          placeholder="vd: 01816"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('facility_code', v ?? '')"
        />
      </FormField>

      <FormField label="Receiver ID">
        <InputText
          :model-value="modelValue.receiver_id"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('receiver_id', v ?? '')"
        />
      </FormField>

      <FormField label="Phiên bản Trục">
        <InputText
          :model-value="modelValue.version"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('version', v ?? '')"
        />
      </FormField>

      <FormField
        label="API base URL (tùy chọn)"
        :help-text="`Bỏ trống sẽ dùng mặc định theo môi trường. Hiện tại: ${config?.api_base_url_effective ?? '—'}`"
      >
        <InputText
          :model-value="modelValue.api_base_url"
          placeholder="https://api-sandbox.emrhub.vn"
          class="w-full"
          @update:model-value="(v: string | undefined) => patch('api_base_url', v ?? '')"
        />
      </FormField>
    </div>

    <FormField
      label="RSA Private Key (PEM)"
      :required="!config?.private_key_set"
      :help-text="config?.private_key_set ? 'Đã lưu private key — bỏ trống để giữ nguyên.' : ''"
    >
      <Textarea
        :model-value="modelValue.private_key"
        rows="5"
        placeholder="-----BEGIN PRIVATE KEY-----"
        class="w-full font-mono text-xs"
        @update:model-value="(v: string | undefined) => patch('private_key', v ?? '')"
      />
    </FormField>

    <div class="flex items-center gap-2">
      <Checkbox
        :model-value="modelValue.is_active"
        :binary="true"
        input-id="sync-active"
        @update:model-value="(v: boolean | undefined) => patch('is_active', !!v)"
      />
      <label for="sync-active" class="text-sm text-text-body">Bật đồng bộ</label>
    </div>

    <div class="flex gap-2">
      <Button label="Lưu cấu hình" icon="pi pi-save" :loading="saving" @click="$emit('save')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Textarea from 'primevue/textarea'
import Checkbox from 'primevue/checkbox'
import FormField from '@/components/common/FormField.vue'
import type { SyncConfig } from '@/types'

export interface ConfigFormModel {
  api_base_url: string
  username: string
  password: string
  facility_code: string
  sender_id: string
  receiver_id: string
  version: string
  private_key: string
  is_active: boolean
}

const props = defineProps<{
  modelValue: ConfigFormModel
  config?: SyncConfig
  saving?: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: ConfigFormModel]
  save: []
}>()

function patch<K extends keyof ConfigFormModel>(key: K, value: ConfigFormModel[K]): void {
  emit('update:modelValue', { ...props.modelValue, [key]: value })
}
</script>
