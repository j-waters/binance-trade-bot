<template>
  <div>
    <div>{{ otherCoin }}</div>
    <div id="wrapper">
      <div id="chart-line2">
        <apexchart
          type="line"
          height="230"
          :options="chartOptions"
          :series="series"
        ></apexchart>
      </div>
      <!--      <div id="chart-line">-->
      <!--        <apexchart-->
      <!--          type="area"-->
      <!--          height="130"-->
      <!--          :options="chartOptionsLine"-->
      <!--          :series="series"-->
      <!--        ></apexchart>-->
      <!--      </div>-->
    </div>
  </div>
</template>

<script lang="ts">
import { defineComponent, PropType } from "vue";
import dayjs, { Dayjs } from "dayjs";
import { ApexOptions } from "apexcharts";
import { ScoutLogEntry, Coin } from "@/models";

export default defineComponent({
  name: "ScoutGraph",
  props: {
    history: {
      type: Object as PropType<ScoutLogEntry[]>,
      required: true
    },
    otherCoin: String
  },
  computed: {
    dates(): string[] {
      return this.history.map(entry =>
        dayjs(entry.datetime).format("MMM DD hh:mm:ss")
      );
    },
    series(): ApexAxisChartSeries {
      return [
        {
          name: "Current ratio",
          data: this.history.map(entry => {
            return { y: entry.current_ratio, x: entry.datetime };
          })
        },
        {
          name: "Target Ratio",
          data: this.history.map(entry => {
            return { y: entry.target_ratio, x: entry.datetime };
          })
        }
      ] as ApexAxisChartSeries;
    },
    chartOptions() {
      return {
        chart: {
          id: "chart2",
          type: "line",
          height: 230,
          toolbar: {
            autoSelected: "pan",
            show: false
          }
        },
        // colors: ["#546E7A"],
        stroke: {
          width: 3
        },
        dataLabels: {
          enabled: false
        },
        fill: {
          opacity: 1
        },
        markers: {
          size: 0
        },
        tooltip: {
          x: {
            format: "yyyy MMM dd hh:mm:ss"
          }
        },
        xaxis: {
          type: "datetime"
          // tooltip: {
          //   formatter(value: string, opts?: object): string {
          //     return dayjs(value).format("YYYY MMM DD hh:mm:ss")
          //   }
          // }
        }
      } as ApexOptions;
    }
  },
  data() {
    return {
      chartOptionsLine: {
        chart: {
          id: "chart1",
          height: 130,
          type: "area",
          brush: {
            target: "chart2",
            enabled: true
          }
          // selection: {
          //   enabled: true,
          //   xaxis: {
          //     min: new Date("19 Jun 2017").getTime(),
          //     max: new Date("14 Aug 2017").getTime()
          //   }
          // }
        },
        colors: ["#008FFB"],
        fill: {
          type: "gradient",
          gradient: {
            opacityFrom: 0.91,
            opacityTo: 0.1
          }
        },
        xaxis: {
          type: "categories",
          categories: this.dates
        },
        yaxis: {
          tickAmount: 2
        }
      } as ApexChart
    };
  }
});
</script>

<style scoped></style>
