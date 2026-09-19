"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ArrowLeft, History, LoaderCircle, PackageCheck, Warehouse } from "lucide-react";
import { Button } from "@/components/ui/button";

type Order = { id:string; market:"wb"|"ozon"; created:string; title:string; sku:string; qty:number; status:string; image?:string; labelNumber?:string };
type Supply = { id:string; name:string; created:string; ordersCount:number; orderIds:string[]; status:string; processed:boolean };
type ApiResult = { history:Order[]; supplies:Supply[] };

function OrderRows({ orders, wbSupply=false }: { orders:Order[]; wbSupply?:boolean }) {
  return <div className="divide-y">{orders.map(order => (
    <div key={`${order.market}-${order.id}`} className="flex items-center gap-3 px-4 py-3">
      <div className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-slate-100">
        {order.image ? <img src={order.image} alt="" className="size-full object-contain"/> : <PackageCheck className="size-5 text-slate-400"/>}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-start justify-between gap-3"><p className="min-w-0 font-medium">{order.title}</p><span className="shrink-0 text-sm font-semibold">{order.qty} шт.</span></div>
        <p className="mt-1 text-sm text-slate-500">Артикул: {order.sku}</p>
        {wbSupply ? order.labelNumber && <p className="mt-1 text-sm font-medium text-slate-700">Стикер WB № {order.labelNumber}</p> : <p className="mt-1 text-sm text-slate-500">Заказ № {order.id}</p>}
        <p className="mt-1 text-sm font-medium text-slate-600">{order.status}</p>
      </div>
    </div>
  ))}</div>;
}

export default function ShipmentHistory() {
  const [data,setData] = useState<ApiResult>();
  const [error,setError] = useState<string>();
  useEffect(() => { fetch(`/api/orders?t=${Date.now()}`, { cache:"no-store", headers:{"Cache-Control":"no-cache"} }).then(async response => { if(!response.ok) throw new Error("Не удалось загрузить историю"); return response.json() as Promise<ApiResult>; }).then(setData).catch(reason => setError(reason instanceof Error ? reason.message : "Ошибка загрузки")); }, []);
  const wbById = useMemo(() => new Map((data?.history??[]).filter(order=>order.market==="wb").map(order=>[order.id,order])), [data]);
  const processedSupplies = useMemo(() => (data?.supplies??[]).filter(supply=>supply.processed), [data]);
  const ozonOrders = useMemo(() => (data?.history??[]).filter(order=>order.market==="ozon" && !["Ожидает сборки","Готов к отгрузке"].includes(order.status)), [data]);

  return <main className="min-h-screen bg-[#f4f7fb] text-slate-950">
    <header className="border-b bg-[#101a2b] text-white"><div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-5 sm:px-7">
      <div className="flex items-center gap-3"><div className="grid size-11 place-items-center rounded-xl bg-cyan-400 text-[#101a2b]"><Warehouse className="size-6"/></div><div><h1 className="text-lg font-bold sm:text-xl">История отгрузок</h1><p className="text-sm text-slate-400">WB и Ozon</p></div></div>
      <Button asChild variant="outline" className="rounded-xl border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"><Link href="/"><ArrowLeft/>Назад</Link></Button>
    </div></header>
    <section className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-7 sm:py-9">
      {!data&&!error&&<div className="flex items-center justify-center gap-2 rounded-2xl border bg-white p-10 text-slate-500"><LoaderCircle className="animate-spin"/>Загружаем историю</div>}
      {error&&<div className="rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">{error}</div>}
      {data&&<>
        <section className="space-y-3"><div className="flex items-center gap-2"><History className="size-5 text-violet-600"/><h2 className="text-lg font-bold">Обработанные поставки WB</h2></div>
          {processedSupplies.length ? <div className="grid gap-4 xl:grid-cols-2">{processedSupplies.map(supply => { const orders=supply.orderIds.map(id=>wbById.get(id)).filter((order):order is Order=>Boolean(order)); return <article key={supply.id} className="overflow-hidden rounded-2xl border bg-white shadow-sm"><div className="border-b p-4"><p className="text-sm font-semibold text-emerald-700">Поставка обработана</p><h3 className="mt-1 font-bold">{supply.name}</h3><p className="mt-1 text-sm text-slate-500">{supply.created} · {supply.ordersCount} заказов</p></div>{orders.length?<OrderRows orders={orders} wbSupply/>:<p className="p-4 text-sm text-slate-500">Состав поставки не получен</p>}</article>; })}</div> : <p className="rounded-xl border bg-white p-5 text-slate-500">Обработанных поставок WB пока нет.</p>}
        </section>
        <section className="space-y-3"><h2 className="text-lg font-bold">История отгрузок Ozon</h2>{ozonOrders.length?<div className="overflow-hidden rounded-2xl border bg-white shadow-sm"><OrderRows orders={ozonOrders}/></div>:<p className="rounded-xl border bg-white p-5 text-slate-500">Завершённых отгрузок Ozon пока нет.</p>}</section>
      </>}
    </section>
  </main>;
}
