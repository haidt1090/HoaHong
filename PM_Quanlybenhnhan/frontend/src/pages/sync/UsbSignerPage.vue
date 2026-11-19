<template>
  <div class="flex flex-col gap-6">
    <PageHeader
      title="Ký USB"
      subtitle="USB token của cơ sở khám, ký qua TokenService trên máy này"
    />

    <SectionCard title="Hướng dẫn" icon="pi pi-book">
      <ol class="flex list-decimal flex-col gap-3 pl-5 text-sm text-text-body">
        <li>Cắm USB của cơ sở khám vào máy đang mở trang Đồng bộ CSDLKSK.</li>
        <li>
          Mở TokenService (biểu tượng ở khay hệ thống, góc phải dưới). Đây là chương trình
          đi kèm Token Manager của Viettel-CA, không phải file tải từ trang này.
        </li>
        <li>
          Trên trang Đồng bộ CSDLKSK, bấm Kiểm tra rồi Đồng bộ. Windows hiện cửa sổ chọn
          chứng thư. Chọn chứng thư của cơ sở khám.
        </li>
        <li>Nhập PIN của USB khi hộp thoại hiện ra. Chữ ký ghi vào CKS_BENH_VIEN.</li>
        <li>CKS_NGUOI_KET_LUAN để trống. Bác sĩ ký phiếu sau trên cổng CSDLKSK.</li>
      </ol>
      <p class="mt-4 text-sm text-text-body">
        Nếu trang báo chưa thấy TokenService, chương trình đó chưa chạy hoặc USB chưa cắm.
        Nhập sai PIN nhiều lần sẽ khóa token.
      </p>
    </SectionCard>
  </div>
</template>

<script setup lang="ts">
import PageHeader from '@/components/common/PageHeader.vue'
import SectionCard from '@/components/common/SectionCard.vue'
</script>
