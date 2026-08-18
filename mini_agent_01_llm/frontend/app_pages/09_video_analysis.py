"""영상 프레임 분석과 음성 안내 화면.

실행 방법:
1. backend 폴더에서 `uvicorn app.main:app --reload`를 실행합니다.
2. frontend 폴더에서 `streamlit run app.py`를 실행합니다.
3. 사이드바의 '1-7. Video analysis and audio'에서 MP4를 선택하거나 웹캠을 촬영합니다.

브라우저가 최대 60초 영상에서 최대 12개의 JPG 프레임만 추출해 FastAPI로 전송합니다.
원본 영상은 FastAPI에 업로드하지 않으며, 분석 후 OpenAI TTS 음성을 자동으로 재생합니다.
"""

import json
import os

import streamlit.components.v1 as components


BACKEND_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")

components.html(
    f'''<!doctype html><html lang="ko"><head><style>
body {{ font-family: sans-serif; margin: 0; color: #1f2937; }} .panel {{ max-width: 800px; padding: 8px; }}
.row {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin:12px 0; }} button,select,input {{ padding:8px 10px; font:inherit; }}
button {{ cursor:pointer; background:#ff4b4b; color:white; border:0; border-radius:5px; }} button:disabled {{ opacity:.55; cursor:default; }}
video {{ width:min(100%,640px); max-height:360px; background:#111; border-radius:6px; }} #status {{ min-height:24px; font-weight:600; }}
#error {{ color:#b42318; white-space:pre-wrap; }} #summary {{ white-space:pre-wrap; line-height:1.6; }} .hidden {{ display:none; }}
</style></head><body><main class="panel">
<h2>영상 장면 요약과 음성 안내</h2><p>MP4 파일을 선택하거나 웹캠으로 최대 60초 영상을 촬영하세요. 원본 영상은 분석 서버로 전송되지 않으며, 브라우저가 추출한 최대 12개 프레임만 전송됩니다.</p>
<div class="row"><label>결과 언어 <select id="language"><option value="ko">한국어</option><option value="en">English</option></select></label><input id="file" type="file" accept="video/mp4"><button id="analyzeFile">MP4 분석</button></div>
<div class="row"><button id="startCamera">웹캠 시작</button><button id="record" disabled>촬영 시작</button></div><video id="video" controls playsinline></video>
<p id="status" aria-live="polite"></p><p id="error" role="alert"></p><section id="result" class="hidden"><h3>통합 장면 요약</h3><p id="summary"></p><audio id="audio" controls></audio></section>
</main><script>
const backendUrl={json.dumps(BACKEND_URL)},video=document.getElementById('video'),fileInput=document.getElementById('file'),language=document.getElementById('language'),status=document.getElementById('status'),error=document.getElementById('error'),result=document.getElementById('result'),summary=document.getElementById('summary'),audio=document.getElementById('audio'),analyzeFile=document.getElementById('analyzeFile'),startCamera=document.getElementById('startCamera'),record=document.getElementById('record');let stream=null,recorder=null,chunks=[];
function setStatus(message){{status.textContent=message}} function showError(message){{error.textContent=message}} function clearResult(){{showError('');result.classList.add('hidden');audio.removeAttribute('src')}}
function waitForMetadata(){{return new Promise((resolve,reject)=>{{if(Number.isFinite(video.duration))return resolve();video.onloadedmetadata=()=>resolve();video.onerror=()=>reject(new Error('브라우저가 이 영상을 재생할 수 없습니다. MP4(H.264)를 사용해 주세요.'))}})}}
async function extractFrames(blob){{const objectUrl=URL.createObjectURL(blob);video.srcObject=null;video.src=objectUrl;await waitForMetadata();const duration=video.duration;if(!Number.isFinite(duration)||duration<=0)throw new Error('영상 길이를 확인할 수 없습니다.');if(duration>60.05)throw new Error('60초 이하의 영상만 분석할 수 있습니다.');const count=Math.min(12,Math.max(1,Math.ceil(duration/5))),canvas=document.createElement('canvas'),context=canvas.getContext('2d'),frames=[];for(let index=0;index<count;index++){{const timestamp=count===1?Math.min(duration/2,.05):Math.min(index*duration/(count-1),Math.max(0,duration-.05));video.currentTime=timestamp;await new Promise((resolve,reject)=>{{video.onseeked=resolve;video.onerror=()=>reject(new Error('프레임을 추출하지 못했습니다.'))}});const scale=Math.min(1,1280/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);context.drawImage(video,0,0,canvas.width,canvas.height);const imageBlob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.8));if(!imageBlob)throw new Error('JPG 프레임 생성에 실패했습니다.');frames.push({{blob:imageBlob,timestamp}})}}URL.revokeObjectURL(objectUrl);return frames}}
async function responseError(response){{try{{const body=await response.json();return body.detail||JSON.stringify(body)}}catch{{return await response.text()||`HTTP ${{response.status}}`}}}}
async function analyze(blob){{clearResult();try{{setStatus('브라우저에서 영상 프레임을 추출하고 있습니다…');const frames=await extractFrames(blob);setStatus(`${{frames.length}}개 프레임을 분석하고 있습니다…`);const form=new FormData();frames.forEach((frame,index)=>form.append('frames',frame.blob,`frame-${{index+1}}.jpg`));form.append('frame_timestamps',JSON.stringify(frames.map(frame=>frame.timestamp)));form.append('language',language.value);const analysisResponse=await fetch(`${{backendUrl}}/api/media/video-analysis`,{{method:'POST',body:form}});if(!analysisResponse.ok)throw new Error(await responseError(analysisResponse));const analysis=await analysisResponse.json();setStatus('음성 안내를 생성하고 있습니다…');const instructions=analysis.language==='ko'?'한국어로 자연스럽고 명료한 장면 안내처럼 말하세요.':'Speak naturally and clearly as a scene guide in English.';const ttsResponse=await fetch(`${{backendUrl}}/api/media/tts`,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{text:analysis.summary,voice:'coral',instructions}})}});if(!ttsResponse.ok)throw new Error(await responseError(ttsResponse));summary.textContent=analysis.summary;audio.src=URL.createObjectURL(await ttsResponse.blob());result.classList.remove('hidden');audio.play().catch(()=>{{}});setStatus(`분석 및 음성 생성 완료 (${{analysis.frame_count}}개 프레임)`)}}catch(exception){{setStatus('');showError(exception.message||'영상 처리 중 오류가 발생했습니다.')}}}}
analyzeFile.addEventListener('click',()=>{{const file=fileInput.files[0];if(!file)return showError('분석할 MP4 파일을 선택하세요.');if(file.type!=='video/mp4')return showError('MP4 파일만 업로드할 수 있습니다.');analyze(file)}});
startCamera.addEventListener('click',async()=>{{clearResult();try{{stream=await navigator.mediaDevices.getUserMedia({{video:true,audio:false}});video.src='';video.srcObject=stream;await video.play();record.disabled=false;setStatus('웹캠 준비 완료. 촬영 시작을 누르세요.')}}catch(exception){{showError(`웹캠을 시작할 수 없습니다: ${{exception.message}}`)}}}});
record.addEventListener('click',()=>{{if(!stream)return;if(recorder&&recorder.state==='recording'){{recorder.stop();record.textContent='촬영 시작';return}}chunks=[];recorder=new MediaRecorder(stream);recorder.ondataavailable=event=>{{if(event.data.size)chunks.push(event.data)}};recorder.onstop=()=>{{stream.getTracks().forEach(track=>track.stop());stream=null;record.disabled=true;analyze(new Blob(chunks,{{type:recorder.mimeType||'video/webm'}}))}};recorder.start();record.textContent='촬영 중지';setStatus('촬영 중입니다. 60초 안에 촬영 중지를 누르세요.');window.setTimeout(()=>{{if(recorder.state==='recording')recorder.stop()}},60000)}});
</script></body></html>''',
    height=690,
    scrolling=True,
)
