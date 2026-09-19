<script setup>
import { onMounted, ref } from 'vue'
import { getJSON } from '../api'
const items = ref([])
onMounted(async () => { items.value = (await getJSON('/api/edges')).items })
</script>
<template>
  <div class="page"><h1>邻接区间</h1>
    <ul><li v-for="(e,i) in items" :key="i">{{ e.a }} — {{ e.b }}</li></ul>
  </div>
</template>
