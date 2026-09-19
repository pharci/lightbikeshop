import { NextRequest, NextResponse } from "next/server";
import { getApiCredentials } from "@/lib/api-credentials";

export const dynamic="force-dynamic";

const wbHeaders=(token:string)=>({Authorization:token,"Content-Type":"application/json"});
const ozonHeaders=(clientId:string,apiKey:string)=>({"Client-Id":clientId,"Api-Key":apiKey,"Content-Type":"application/json"});
const chunks=<T,>(items:T[],size:number)=>Array.from({length:Math.ceil(items.length/size)},(_,index)=>items.slice(index*size,(index+1)*size));
const binaryToBase64=(value:string)=>{let result="";for(let index=0;index<value.length;index+=8192){result+=String.fromCharCode(...Array.from(value.slice(index,index+8192),char=>char.charCodeAt(0)&255))}return btoa(result)};

async function checkedJson(url:string,init:RequestInit,label:string){const response=await fetch(url,init);const text=await response.text();let data:unknown={};try{data=text?JSON.parse(text):{}}catch{data={message:text}}if(!response.ok){const message=typeof data==="object"&&data&&"message"in data?String((data as{message?:unknown}).message):`${label}: ошибка ${response.status}`;throw new Error(message)}return data as Record<string,unknown>}

export async function POST(request:NextRequest){
  if(request.headers.get("sec-fetch-site")==="cross-site")return NextResponse.json({error:"Запрос отклонён"},{status:403});
  try{
    const credentials=getApiCredentials();
    const body=await request.json() as{market?:"wb"|"ozon";ids?:string[]};
    const ids=[...new Set((body.ids??[]).map(String))].slice(0,1000);
    if(!ids.length)return NextResponse.json({error:"Нет выбранных заказов"},{status:400});
    if(body.market==="wb"){
      const token=credentials.wbToken;if(!token)return NextResponse.json({error:"WB не подключён"},{status:400});
      const numericIds=ids.map(Number).filter(Number.isSafeInteger);if(numericIds.length!==ids.length)return NextResponse.json({error:"Некорректные номера WB"},{status:400});
      const files:Array<{name:string;type:string;dataUrl:string}>=[];
      for(const part of chunks(numericIds,100)){const data=await checkedJson("https://marketplace-api.wildberries.ru/api/v3/orders/stickers?type=png&width=58&height=40",{method:"POST",headers:wbHeaders(token),body:JSON.stringify({orders:part})},"WB");for(const sticker of (data.stickers??[]) as Array<{orderId?:number;file?:string}>){if(sticker.file)files.push({name:`wb-${sticker.orderId??files.length+1}.png`,type:"image/png",dataUrl:`data:image/png;base64,${sticker.file}`})}}
      return NextResponse.json({market:"wb",files});
    }
    if(body.market==="ozon"){
      const clientId=credentials.ozonClientId,apiKey=credentials.ozonApiKey;if(!clientId||!apiKey)return NextResponse.json({error:"Ozon не подключён"},{status:400});
      const files:Array<{name:string;type:string;dataUrl:string}>=[];
      for(const part of chunks(ids,20)){const data=await checkedJson("https://api-seller.ozon.ru/v2/posting/fbs/package-label",{method:"POST",headers:ozonHeaders(clientId,apiKey),body:JSON.stringify({posting_number:part})},"Ozon");const content=String(data.file_content??"");if(content)files.push({name:String(data.file_name??`ozon-labels-${files.length+1}.pdf`),type:String(data.content_type??"application/pdf"),dataUrl:`data:${String(data.content_type??"application/pdf")};base64,${binaryToBase64(content)}`})}
      return NextResponse.json({market:"ozon",files});
    }
    return NextResponse.json({error:"Неизвестный маркетплейс"},{status:400});
  }catch(error){return NextResponse.json({error:error instanceof Error?error.message:"Не удалось получить этикетки"},{status:500})}
}
