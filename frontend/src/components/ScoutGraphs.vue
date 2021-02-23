<template>
  <div>
    <scout-graph
      v-for="coin in coins"
      :history="histories[coin]"
      :other-coin="coin"
      :key="coin"
    ></scout-graph>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from "vue";
import ScoutGraph from "@/components/ScoutGraph.vue";
import { groupBy } from "@/util";
import { Coin, ScoutLogsGrouped } from "@/models";

export default defineComponent({
  name: "ScoutGraphs",
  components: { ScoutGraph },
  props: {
    histories: {
      type: Object as PropType<ScoutLogsGrouped>
    }
  },
  computed: {
    // selectedHistories(): ScoutLogsGrouped | null {
    //   if (
    //     !this.histories ||
    //     !this.selectedCoin ||
    //     this.histories[this.selectedCoin.symbol] == null
    //   ) {
    //     return null;
    //   }
    //
    //   return groupBy(
    //     this.histories[this.selectedCoin.symbol],
    //     entry => entry.to_coin.symbol
    //   );
    // },
    coins(): string[] {
      if (!this.histories) {
        return [];
      }
      return Object.keys(this.histories);
    }
  },
});
</script>

<style scoped></style>
