<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
const dirText = (d) => d === 'outbound' ? '去程' : d === 'inbound' ? '返程' : ''
onMounted(async () => { items.value = (await getJSON('/api/history')).items })
</script>
<template>
  <div class="page"><h1>试算记录</h1>
    <table>
      <tr><th>编号</th><th>类型</th><th>方向</th><th>时间</th><th></th></tr>
      <tr v-for="h in items" :key="h.id">
        <td>#{{ h.id }}</td>
        <td>{{ h.kind === 'roundtrip' ? '往返联程' : '单程' }}</td>
        <td>{{ dirText(h.result?.direction) }}</td>
        <td>{{ h.created_at }}</td>
        <td><router-link :to="`/history/${h.id}`">打开</router-link></td>
      </tr>
    </table>
  </div>
</template>
