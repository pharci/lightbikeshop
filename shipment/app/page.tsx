"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowDownToLine,
  CheckCircle2,
  CloudUpload,
  History,
  LoaderCircle,
  PackageCheck,
  Printer,
  QrCode,
  RefreshCw,
  Warehouse,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Toaster } from "@/components/ui/sonner";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

type Order = {
  id: string;
  market: "wb" | "ozon";
  created: string;
  title: string;
  sku: string;
  qty: number;
  status: string;
  image?: string;
  labelNumber?: string;
};
type Supply = {
  id: string;
  name: string;
  created: string;
  ordersCount: number;
  orderIds: string[];
  items: Order[];
  status: string;
  processed: boolean;
  barcode: string;
  qrDataUrl?: string;
  boxStickers: Array<{ barcode: string; dataUrl: string }>;
};
type ApiResult = {
  orders: Order[];
  history: Order[];
  supplies: Supply[];
  connections: { wb: boolean; ozon: boolean };
  errors: Record<string, string>;
  syncedAt: string;
};
type FileArtifact = { name: string; type: string; dataUrl: string };
type FormationResult = {
  wb: Array<{
    id: string;
    ordersCount: number;
    cargoType: number;
    boxIds: string[];
    cargoPlaces: Array<{ id: string; orderIds: string[] }>;
    boxStickers: FileArtifact[];
    orderStickers: FileArtifact[];
    supplyQr?: FileArtifact;
    error?: string;
  }>;
  ozon: Array<{
    id: string;
    deliveryMethodId: number;
    ordersCount: number;
    labels: FileArtifact[];
    status: string;
    orderIds: string[];
    error?: string;
  }>;
  warnings: string[];
};

export default function Home() {
  const [orders, setOrders] = useState<Order[]>([]);
  const [supplies, setSupplies] = useState<Supply[]>([]);
  const [connections, setConnections] = useState({ wb: false, ozon: false });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [syncedAt, setSyncedAt] = useState<string>();
  const [loading, setLoading] = useState(true);
  const [forming, setForming] = useState<"wb" | "ozon" | null>(null);
  const [formation, setFormation] = useState<FormationResult>();
  const [uploadingSupply, setUploadingSupply] = useState<string>();
  const [confirmedOzon, setConfirmedOzon] = useState<Order[]>([]);

  const loadData = useCallback(async (showToast = false) => {
    setLoading(true);
    try {
      try {
        const localOrders = JSON.parse(
          localStorage.getItem("confirmedOzonOrders") || "[]",
        ) as Order[];
        const orderIds = localOrders.map((order) => order.id).filter(Boolean);
        if (orderIds.length) {
          await fetch(`/shipment/api/orders/confirmed?t=${Date.now()}`, {
            method: "POST",
            cache: "no-store",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              confirmation: "SYNC_CONFIRMED_OZON",
              orderIds,
            }),
          });
        }
      } catch {
        localStorage.removeItem("confirmedOzonOrders");
      }
      const response = await fetch(`/shipment/api/orders?t=${Date.now()}`, {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!response.ok) throw new Error("Не удалось получить заказы");
      const data = (await response.json()) as ApiResult;
      setOrders(data.orders ?? []);
      const confirmedFromServer = (data.orders ?? []).filter(
        (order) =>
          order.market === "ozon" &&
          order.status === "Подтверждённая отгрузка",
      );
      setConfirmedOzon(confirmedFromServer);
      localStorage.setItem(
        "confirmedOzonOrders",
        JSON.stringify(confirmedFromServer),
      );
      setSupplies(data.supplies ?? []);
      setConnections(data.connections);
      setErrors(data.errors ?? {});
      setSyncedAt(data.syncedAt);
      if (showToast) toast.success("Данные обновлены");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка обновления");
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => void loadData(), 0);
    return () => window.clearTimeout(timer);
  }, [loadData]);

  const wbOrders = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.market === "wb" && order.status === "Собран в МойСклад",
      ),
    [orders],
  );
  const wbWaiting = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.market === "wb" &&
          order.status === "Ожидает сборки через МойСклад",
      ),
    [orders],
  );
  const ozonReady = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.market === "ozon" &&
          order.status === "Готов к отгрузке" &&
          !confirmedOzon.some((confirmed) => confirmed.id === order.id),
      ),
    [orders, confirmedOzon],
  );
  const ozonWaiting = useMemo(
    () =>
      orders.filter(
        (order) =>
          order.market === "ozon" &&
          order.status !== "Готов к отгрузке" &&
          order.status !== "Подтверждённая отгрузка",
      ),
    [orders],
  );
  const activeSupplies = useMemo(
    () => supplies.filter((supply) => !supply.processed),
    [supplies],
  );
  const activeSupplyIds = useMemo(
    () => new Set(activeSupplies.map((supply) => supply.id)),
    [activeSupplies],
  );
  const visibleFormationWb = useMemo(
    () =>
      (formation?.wb ?? []).filter(
        (item) => item.error || !activeSupplyIds.has(item.id),
      ),
    [formation, activeSupplyIds],
  );
  const showFormation = Boolean(
    formation &&
      (formation.warnings.length ||
        visibleFormationWb.length ||
        formation.ozon.length),
  );
  const downloadFile = (file: FileArtifact) => {
    const anchor = document.createElement("a");
    anchor.href = file.dataUrl;
    anchor.download = file.name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
  };
  const printImages = (files: FileArtifact[]) => {
    const images = files.filter((file) => file.type.startsWith("image/"));
    if (!images.length) {
      toast.error("Этикетки не получены");
      return;
    }
    const popup = window.open("", "_blank");
    if (!popup) {
      toast.error("Разрешите всплывающие окна для печати");
      return;
    }
    popup.document.write(
      `<html><head><title>Этикетки</title><style>@page{margin:5mm}body{margin:0;display:grid;grid-template-columns:repeat(2,58mm);gap:3mm;justify-content:center}img{width:58mm;height:40mm;object-fit:contain;break-inside:avoid}</style></head><body>${images.map((file) => `<img src="${file.dataUrl}"/>`).join("")}<script>window.onload=()=>window.print()<\/script></body></html>`,
    );
    popup.document.close();
  };

  const formShipments = async (market: "wb" | "ozon", boxCount = 1) => {
    setForming(market);
    setFormation(undefined);
    try {
      const response = await fetch(`/shipment/api/shipments/form?t=${Date.now()}`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmation: "FORM_SHIPMENTS",
          wbOrderIds: market === "wb" ? wbOrders.map((order) => order.id) : [],
          wbBoxCount: market === "wb" ? boxCount : 0,
          ozonOrderIds:
            market === "ozon" ? ozonReady.map((order) => order.id) : [],
        }),
      });
      const data = (await response.json()) as FormationResult & {
        error?: string;
      };
      if (!response.ok)
        throw new Error(data.error || "Не удалось сформировать отгрузки");
      const marketErrors =
        market === "ozon"
          ? (data.ozon ?? []).filter((item) => item.error)
          : (data.wb ?? []).filter((item) => item.error);
      if (marketErrors.length) {
        throw new Error(
          marketErrors[0].error ||
            (market === "ozon"
              ? "Ozon не подтвердил товары"
              : "WB не сформировал поставку"),
        );
      }
      if (market === "wb" && !(data.wb ?? []).length) {
        throw new Error(
          "WB не сформировал грузоместо и не перевёл поставку в доставку",
        );
      }
      if (market === "ozon") {
        const confirmedIds = new Set(
          (data.ozon ?? []).flatMap((item) => item.orderIds ?? []),
        );
        const justConfirmed = ozonReady.filter((order) => confirmedIds.has(order.id));
        setConfirmedOzon((current) => {
          const merged = [...justConfirmed, ...current.filter((item) => !confirmedIds.has(item.id))];
          localStorage.setItem("confirmedOzonOrders", JSON.stringify(merged));
          return merged;
        });
      }
      setFormation(data);
      toast.success(
        market === "wb"
          ? "Поставка WB сформирована"
          : "Отгрузка Ozon подтверждена",
      );
      await loadData();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : "Ошибка формирования",
      );
    } finally {
      setForming(null);
    }
  };
  const uploadSupplyToMoySklad = async (supply: Supply) => {
    setUploadingSupply(supply.id);
    try {
      const images = [
        ...supply.boxStickers.map((sticker) => ({ dataUrl: sticker.dataUrl })),
        ...(supply.qrDataUrl ? [{ dataUrl: supply.qrDataUrl }] : []),
      ];
      const response = await fetch("/shipment/api/moysklad/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmation: "UPLOAD_WB_TO_MOYSKLAD",
          supplyId: supply.id,
          images,
        }),
      });
      const data = (await response.json()) as {
        error?: string;
        uploaded?: number;
        skipped?: number;
        failed?: number;
      };
      if (!response.ok)
        throw new Error(data.error || "Не удалось передать файлы");
      if (data.failed)
        toast.warning(
          `Передано: ${data.uploaded}, уже было: ${data.skipped}, ошибок: ${data.failed}`,
        );
      else
        toast.success(
          `Файл передан в ${Number(data.uploaded) + Number(data.skipped)} заказов МоегоСклада`,
        );
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Ошибка передачи");
    } finally {
      setUploadingSupply(undefined);
    }
  };


  return (
    <main className="min-h-screen bg-[#f4f7fb] text-slate-950">
      <header className="border-b bg-[#101a2b] text-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-3 px-4 py-5 sm:px-7">
          <div className="flex items-center gap-3">
            <div className="grid size-11 place-items-center rounded-xl bg-cyan-400 text-[#101a2b]">
              <Warehouse className="size-6" />
            </div>
            <div>
              <h1 className="text-lg font-bold sm:text-xl">
                Формирование отгрузок
              </h1>
              <p className="text-sm text-slate-400">Wildberries и Ozon</p>
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              asChild
              variant="outline"
              className="rounded-xl border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
            >
              <Link href="/history">
                <History />
                <span className="hidden sm:inline">История</span>
              </Link>
            </Button>
            <Button
              variant="outline"
              className="rounded-xl border-white/20 bg-white/10 text-white hover:bg-white/20 hover:text-white"
              disabled={loading || Boolean(forming)}
              onClick={() => void loadData(true)}
            >
              <RefreshCw className={loading ? "animate-spin" : ""} />
              <span className="hidden sm:inline">Обновить</span>
            </Button>
          </div>
        </div>
      </header>

      <section className="mx-auto max-w-6xl space-y-5 px-4 py-6 sm:px-7 sm:py-9">
        <div className="grid gap-4 sm:grid-cols-2">
          <article className="rounded-2xl border border-violet-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-violet-700">
                  Wildberries
                </p>
                <div className="mt-2 text-4xl font-bold">
                  {loading ? "—" : wbOrders.length}
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  собраны в МойСклад
                </p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${connections.wb ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}
              >
                {connections.wb ? "Подключён" : "Не подключён"}
              </span>
            </div>
            {wbWaiting.length > 0 && (
              <p className="mt-4 border-t pt-4 text-sm font-medium text-amber-700">
                Ожидают сборки через МойСклад: {wbWaiting.length}
              </p>
            )}
          </article>
          <article className="rounded-2xl border border-blue-200 bg-white p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-blue-700">Ozon</p>
                <div className="mt-2 text-4xl font-bold">
                  {loading ? "—" : ozonReady.length}
                </div>
                <p className="mt-1 text-sm text-slate-500">готовы к отгрузке</p>
              </div>
              <span
                className={`rounded-full px-3 py-1 text-sm font-semibold ${connections.ozon ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}
              >
                {connections.ozon ? "Подключён" : "Не подключён"}
              </span>
            </div>
            {ozonWaiting.length > 0 && (
              <p className="mt-4 border-t pt-4 text-sm font-medium text-amber-700">
                Ожидают сборки через МойСклад: {ozonWaiting.length}
              </p>
            )}
          </article>
        </div>

        {Object.keys(errors).length > 0 && (
          <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {Object.entries(errors).map(([key, value]) => (
              <p key={key}>
                <strong>{key.toUpperCase()}:</strong> {value}
              </p>
            ))}
          </div>
        )}

        <div className="rounded-2xl bg-[#101a2b] p-5 text-white shadow-lg sm:p-7">
          <div>
            <div className="flex items-center gap-2 text-cyan-300">
              <PackageCheck className="size-5" />
              <span className="text-sm font-bold uppercase tracking-wide">
                Перед поездкой в ПВЗ
              </span>
            </div>
            <h2 className="mt-3 text-2xl font-bold">Выберите маркетплейс</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Проверьте, что товары действительно собраны. WB и Ozon формируются
              независимо друг от друга.
            </p>
            {syncedAt && (
              <p className="mt-3 text-sm text-slate-400">
                Данные обновлены{" "}
                {new Date(syncedAt).toLocaleTimeString("ru-RU", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            )}
          </div>
          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  size="lg"
                  className="h-14 rounded-xl bg-[#1267f2] px-7 text-base font-bold hover:bg-blue-500"
                  disabled={loading || Boolean(forming) || !ozonReady.length}
                >
                  {forming === "ozon" ? (
                    <LoaderCircle className="animate-spin" />
                  ) : (
                    <PackageCheck />
                  )}
                  {forming === "ozon"
                    ? "Подтверждаем Ozon…"
                    : `Подтвердить Ozon · ${ozonReady.length}`}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    Подтвердить отгрузки Ozon?
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    В обработку попадёт {ozonReady.length} заказов со статусом
                    «Готов к отгрузке». Отгрузки будут разделены по складам.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Отмена</AlertDialogCancel>
                  <AlertDialogAction
                    className="bg-[#1267f2]"
                    onClick={() => void formShipments("ozon")}
                  >
                    Да, подтвердить Ozon
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div className="overflow-hidden rounded-xl border border-violet-400/20 bg-white/10">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <p className="font-semibold">Заказы WB</p>
                <span className="rounded-full bg-violet-500/20 px-2.5 py-1 text-sm text-violet-200">
                  {wbOrders.length}
                </span>
              </div>
              <div className="max-h-64 divide-y divide-white/10 overflow-y-auto">
                <div className="bg-violet-500/10 px-4 py-2 text-xs font-bold uppercase tracking-wide text-violet-200">
                  Собраны в МойСклад
                </div>
                {wbOrders.map((order) => (
                  <div key={order.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/10">
                      {order.image ? (
                        <img src={order.image} alt="" className="size-full object-contain" />
                      ) : (
                        <PackageCheck className="size-5 text-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold leading-5">{order.title}</p>
                      <p className="mt-1 text-xs text-slate-400">Артикул: {order.sku}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        Заказ № {order.id}
                        {order.labelNumber ? ` · Стикер № ${order.labelNumber}` : ""}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-violet-200">{order.qty} шт.</span>
                  </div>
                ))}
                {!loading && !wbOrders.length && (
                  <p className="px-4 py-5 text-sm text-slate-400">
                    Нет заказов, собранных в МойСклад
                  </p>
                )}
                <div className="flex items-center justify-between bg-amber-500/10 px-4 py-2 text-xs font-bold uppercase tracking-wide text-amber-200">
                  <span>Ожидает сборки через МойСклад</span>
                  <span>{wbWaiting.length}</span>
                </div>
                {wbWaiting.map((order) => (
                  <div key={`waiting-${order.id}`} className="flex items-center gap-3 px-4 py-3 opacity-75">
                    <div className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/10">
                      {order.image ? (
                        <img src={order.image} alt="" className="size-full object-contain" />
                      ) : (
                        <PackageCheck className="size-5 text-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold leading-5">{order.title}</p>
                      <p className="mt-1 text-xs text-slate-400">Артикул: {order.sku}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        Заказ № {order.id}
                        {order.labelNumber ? ` · Стикер № ${order.labelNumber}` : ""}
                      </p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-amber-200">{order.qty} шт.</span>
                  </div>
                ))}
                {!loading && !wbWaiting.length && (
                  <p className="px-4 py-4 text-sm text-slate-400">Нет заказов, ожидающих сборки</p>
                )}
              </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-blue-400/20 bg-white/10">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                <p className="font-semibold">Заказы Ozon</p>
                <span className="rounded-full bg-blue-500/20 px-2.5 py-1 text-sm text-blue-200">
                  {ozonReady.length}
                </span>
              </div>
              <div className="max-h-64 divide-y divide-white/10 overflow-y-auto">
                <div className="bg-blue-500/10 px-4 py-2 text-xs font-bold uppercase tracking-wide text-blue-200">
                  Готовы к отгрузке
                </div>
                {ozonReady.map((order) => (
                  <div key={order.id} className="flex items-center gap-3 px-4 py-3">
                    <div className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/10">
                      {order.image ? (
                        <img src={order.image} alt="" className="size-full object-contain" />
                      ) : (
                        <PackageCheck className="size-5 text-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold leading-5">{order.title}</p>
                      <p className="mt-1 text-xs text-slate-400">Артикул: {order.sku}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">Заказ № {order.id}</p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-blue-200">{order.qty} шт.</span>
                  </div>
                ))}
                {!loading && !ozonReady.length && (
                  <p className="px-4 py-5 text-sm text-slate-400">
                    Нет заказов, готовых к отгрузке
                  </p>
                )}
                <div className="flex items-center justify-between bg-amber-500/10 px-4 py-2 text-xs font-bold uppercase tracking-wide text-amber-200">
                  <span>Ожидает сборки через МойСклад</span>
                  <span>{ozonWaiting.length}</span>
                </div>
                {ozonWaiting.map((order) => (
                  <div
                    key={`waiting-${order.id}`}
                    className="flex items-center gap-3 px-4 py-3 opacity-75"
                  >
                    <div className="grid size-12 shrink-0 place-items-center overflow-hidden rounded-lg bg-white/10">
                      {order.image ? (
                        <img src={order.image} alt="" className="size-full object-contain" />
                      ) : (
                        <PackageCheck className="size-5 text-slate-400" />
                      )}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold leading-5">{order.title}</p>
                      <p className="mt-1 text-xs text-slate-400">Артикул: {order.sku}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">Заказ № {order.id} · {order.status}</p>
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-amber-200">{order.qty} шт.</span>
                  </div>
                ))}
                {!loading && !ozonWaiting.length && (
                  <p className="px-4 py-4 text-sm text-slate-400">
                    Нет заказов, ожидающих сборки
                  </p>
                )}
              </div>
            </div>
          </div>
          {!loading && !wbOrders.length && !ozonReady.length && (
            <div className="mt-5 rounded-xl bg-white/10 px-4 py-3 text-sm text-slate-300">
              Готовых заказов для формирования сейчас нет.
            </div>
          )}
        </div>

        {confirmedOzon.length > 0 && (
          <section className="rounded-2xl border border-emerald-200 bg-white p-5 shadow-sm sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-sm font-bold uppercase tracking-wide text-emerald-700">Ozon</p>
                <h2 className="mt-1 text-xl font-bold">Подтверждённая отгрузка</h2>
              </div>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-bold text-emerald-800">
                {confirmedOzon.length}
              </span>
            </div>
            <div className="mt-4 divide-y rounded-xl border">
              {confirmedOzon.map((order) => (
                <div key={`confirmed-${order.id}`} className="flex items-center gap-3 p-3">
                  <div className="grid size-16 shrink-0 place-items-center overflow-hidden rounded-lg bg-slate-100">
                    {order.image ? (
                      <img src={order.image} alt="" className="size-full object-contain" />
                    ) : (
                      <PackageCheck className="size-7 text-slate-400" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold leading-5">{order.title}</p>
                    <p className="mt-1 text-sm text-slate-500">Артикул: {order.sku}</p>
                    <p className="mt-0.5 text-xs text-slate-400">Заказ № {order.id}</p>
                  </div>
                  <span className="shrink-0 text-sm font-bold text-emerald-700">{order.qty} шт.</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {formation && showFormation && (
          <section className="space-y-4 rounded-2xl border bg-white p-5 shadow-sm">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-5 text-emerald-600" />
              <h2 className="text-lg font-bold">Результат формирования</h2>
            </div>
            <p className="text-sm text-slate-500">
              Скачайте файлы перед закрытием страницы.
            </p>
            {formation.warnings.map((warning) => (
              <div
                key={warning}
                className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800"
              >
                {warning}
              </div>
            ))}
            <div className="grid gap-4 xl:grid-cols-2">
              {visibleFormationWb.map((item) => (
                <article
                  key={`wb-${item.id}-${item.cargoType}`}
                  className={`rounded-xl border p-4 ${item.error ? "border-rose-200 bg-rose-50" : "border-violet-200 bg-violet-50"}`}
                >
                  <p className="text-sm font-bold text-violet-700">
                    Wildberries
                  </p>
                  <h3 className="mt-1 font-bold">Поставка {item.id}</h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.ordersCount} заказов · {item.boxIds.length}{" "}
                    {item.boxIds.length === 1 ? "грузоместо" : "грузоместа"}
                  </p>
                  {item.error ? (
                    <p className="mt-3 text-sm font-semibold text-rose-700">
                      {item.error}
                    </p>
                  ) : (
                    <>
                      <div className="mt-4 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant="outline"
                          className="bg-white"
                          onClick={() => printImages(item.orderStickers)}
                        >
                          <Printer />
                          Заказы
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="bg-white"
                          onClick={() => printImages(item.boxStickers)}
                        >
                          <Printer />
                          Грузоместо
                        </Button>
                        <Button
                          size="sm"
                          className="bg-[#7c3aed]"
                          disabled={!item.supplyQr}
                          onClick={() =>
                            item.supplyQr && downloadFile(item.supplyQr)
                          }
                        >
                          <QrCode />
                          QR поставки
                        </Button>
                      </div>
                      <div className="mt-4 grid gap-3 sm:grid-cols-2">
                        {item.boxStickers.map((file, index) => (
                          <div
                            key={file.name}
                            className="rounded-xl border bg-white p-3"
                          >
                            <p className="mb-2 text-sm font-semibold">
                              Стикер грузоместа {index + 1}
                            </p>
                            <div className="flex min-h-36 items-center justify-center rounded-lg bg-slate-50 p-2">
                              <img
                                src={file.dataUrl}
                                alt={`Стикер грузоместа ${index + 1}`}
                                className="max-h-40 max-w-full"
                              />
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              className="mt-3 w-full"
                              onClick={() => downloadFile(file)}
                            >
                              <ArrowDownToLine />
                              Скачать
                            </Button>
                          </div>
                        ))}
                        {item.supplyQr && (
                          <div className="rounded-xl border bg-white p-3">
                            <p className="mb-2 text-sm font-semibold">
                              QR поставки
                            </p>
                            <div className="flex min-h-36 items-center justify-center rounded-lg bg-slate-50 p-2">
                              <img
                                src={item.supplyQr.dataUrl}
                                alt={`QR поставки ${item.id}`}
                                className="max-h-40 max-w-full"
                              />
                            </div>
                            <Button
                              size="sm"
                              variant="outline"
                              className="mt-3 w-full"
                              onClick={() =>
                                item.supplyQr && downloadFile(item.supplyQr)
                              }
                            >
                              <ArrowDownToLine />
                              Скачать
                            </Button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </article>
              ))}
              {formation.ozon.map((item) => (
                <article
                  key={`ozon-${item.id}-${item.deliveryMethodId}`}
                  className={`rounded-xl border p-4 ${item.error ? "border-rose-200 bg-rose-50" : "border-blue-200 bg-blue-50"}`}
                >
                  <p className="text-sm font-bold text-blue-700">Ozon</p>
                  <h3 className="mt-1 font-bold">
                    {item.error
                      ? "Отгрузка не подтверждена"
                      : `Отгрузка ${item.id}`}
                  </h3>
                  <p className="mt-1 text-sm text-slate-600">
                    {item.ordersCount} заказов · статус {item.status}
                  </p>
                  {item.error ? (
                    <p className="mt-3 text-sm font-semibold text-rose-700">
                      {item.error}
                    </p>
                  ) : (
                    <div className="mt-4 flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        className="bg-white"
                        onClick={() => item.labels.forEach(downloadFile)}
                      >
                        <ArrowDownToLine />
                        Этикетки
                      </Button>
                    </div>
                  )}
                </article>
              ))}
            </div>
          </section>
        )}

        {activeSupplies.length > 0 && (
          <section className="space-y-3">
            <h2 className="text-lg font-bold">
              Стикеры грузомест и поставок WB
            </h2>
            <div className="grid gap-4 xl:grid-cols-2">
              {activeSupplies.map((supply) => {
                const items = supply.items ?? [];
                const formedSupply = formation?.wb.find(
                  (item) => item.id === supply.id && !item.error,
                );
                return (
                  <article
                    key={supply.id}
                    className="rounded-2xl border bg-white p-5 shadow-sm"
                  >
                    <p className="text-sm font-semibold text-orange-700">
                      {supply.status}
                    </p>
                    <h3 className="mt-2 font-bold">{supply.name}</h3>
                    <p className="mt-2 text-sm text-slate-500">
                      {supply.ordersCount} заказов · {supply.barcode}
                    </p>
                    {items.length > 0 && (
                      <div className="mt-4 overflow-hidden rounded-xl border">
                        <p className="border-b bg-slate-50 px-3 py-2 text-sm font-semibold">
                          Товары в поставке
                        </p>
                        <div className="max-h-48 divide-y overflow-y-auto">
                          {items.map((order) => (
                            <div key={order.id} className="flex items-center gap-3 px-3 py-3">
                              <div className="grid size-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-slate-100">
                                {order.image ? (
                                  <img src={order.image} alt="" className="size-full object-contain" />
                                ) : (
                                  <PackageCheck className="size-5 text-slate-400" />
                                )}
                              </div>
                              <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold leading-5">{order.title}</p>
                                <p className="mt-1 text-xs text-slate-500">Артикул: {order.sku}</p>
                                {order.labelNumber && (
                                  <p className="mt-0.5 text-xs font-medium text-slate-700">
                                    Стикер № {order.labelNumber}
                                  </p>
                                )}
                              </div>
                              <span className="shrink-0 text-sm font-semibold">{order.qty} шт.</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {!items.length && (
                      <div className="mt-4 rounded-xl border border-dashed px-3 py-4 text-sm text-slate-500">
                        Состав поставки пока не получен
                      </div>
                    )}
                    {formedSupply?.orderStickers.length ? (
                      <Button
                        variant="outline"
                        className="mt-4 w-full rounded-xl bg-white"
                        onClick={() => printImages(formedSupply.orderStickers)}
                      >
                        <Printer />
                        Этикетки заказов
                      </Button>
                    ) : null}
                    <AlertDialog>
                      <AlertDialogTrigger asChild>
                        <Button
                          className="mt-4 w-full rounded-xl bg-emerald-700 hover:bg-emerald-600"
                          disabled={
                            uploadingSupply === supply.id ||
                            !supply.orderIds.length ||
                            !supply.boxStickers.length ||
                            !supply.qrDataUrl
                          }
                        >
                          {uploadingSupply === supply.id ? (
                            <LoaderCircle className="animate-spin" />
                          ) : (
                            <CloudUpload />
                          )}
                          {uploadingSupply === supply.id
                            ? "Передаём…"
                            : "Передать коды в МойСклад"}
                        </Button>
                      </AlertDialogTrigger>
                      <AlertDialogContent>
                        <AlertDialogHeader>
                          <AlertDialogTitle>
                            Передать коды в МойСклад?
                          </AlertDialogTitle>
                          <AlertDialogDescription>
                            Общий PDF со стикерами грузомест и QR поставки будет
                            прикреплён ко всем {supply.orderIds.length}{" "}
                            связанным WB-заказам. Уже загруженный файл повторно
                            не добавится.
                          </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                          <AlertDialogCancel>Отмена</AlertDialogCancel>
                          <AlertDialogAction
                            className="bg-emerald-700"
                            onClick={() => void uploadSupplyToMoySklad(supply)}
                          >
                            Передать коды
                          </AlertDialogAction>
                        </AlertDialogFooter>
                      </AlertDialogContent>
                    </AlertDialog>
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      {supply.boxStickers.map((sticker, index) => (
                        <div
                          key={`${supply.id}-${sticker.barcode}`}
                          className="rounded-xl border bg-slate-50 p-3"
                        >
                          <p className="mb-2 text-sm font-semibold">
                            Стикер грузоместа {index + 1}
                          </p>
                          <div className="flex min-h-36 items-center justify-center rounded-lg bg-white p-2">
                            <img
                              src={sticker.dataUrl}
                              alt={`Стикер грузоместа ${sticker.barcode}`}
                              className="max-h-40 max-w-full"
                            />
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            className="mt-3 w-full bg-white"
                            onClick={() =>
                              downloadFile({
                                name: `Грузоместо-${sticker.barcode}.png`,
                                type: "image/png",
                                dataUrl: sticker.dataUrl,
                              })
                            }
                          >
                            <ArrowDownToLine />
                            Скачать
                          </Button>
                        </div>
                      ))}
                      {supply.qrDataUrl && (
                        <div className="rounded-xl border bg-slate-50 p-3">
                          <p className="mb-2 text-sm font-semibold">
                            QR поставки
                          </p>
                          <div className="flex min-h-36 items-center justify-center rounded-lg bg-white p-2">
                            <img
                              src={supply.qrDataUrl}
                              alt={`QR поставки ${supply.barcode}`}
                              className="max-h-40 max-w-full"
                            />
                          </div>
                          <Button
                            size="sm"
                            className="mt-3 w-full bg-[#7c3aed]"
                            onClick={() =>
                              supply.qrDataUrl &&
                              downloadFile({
                                name: `Поставка-${supply.barcode}.png`,
                                type: "image/png",
                                dataUrl: supply.qrDataUrl,
                              })
                            }
                          >
                            <QrCode />
                            Скачать QR
                          </Button>
                        </div>
                      )}
                    </div>
                    {!supply.boxStickers.length && !supply.qrDataUrl && (
                      <div className="mt-4 rounded-xl border border-dashed bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
                        Стикеры ещё формируются на стороне WB. Нажмите
                        «Обновить» через несколько секунд.
                      </div>
                    )}
                    {(!supply.boxStickers.length || !supply.qrDataUrl) && (
                      <Button
                        variant="outline"
                        className="mt-3 w-full rounded-xl bg-white"
                        disabled={loading}
                        onClick={() => void loadData(true)}
                      >
                        <RefreshCw className={loading ? "animate-spin" : ""} />
                        Повторить получение кодов
                      </Button>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
        )}
      </section>
      <Toaster richColors position="bottom-right" />
    </main>
  );
}
