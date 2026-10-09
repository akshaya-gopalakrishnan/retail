// NODE_PATH=<playwright node_modules> node --test retail/tests/test_retail_keyboard_browser.cjs
// Real DOM/jQuery regression: closed Air Datepicker panels still match :visible.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {chromium}=require('playwright');
test('off-screen closed calendars do not block Enter or Shift+Enter; active calendars do',async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setContent('<main><input id="first"><input id="second"><input id="scan"></main><div class="datepicker" style="position:absolute;left:-100000px;width:250px;height:250px;opacity:0"></div>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../../frappe/frappe/public/js/lib/jquery/jquery.min.js')});
  await page.evaluate(()=>{
   window.__=s=>s;
   window.frappe={provide:p=>p.split('.').reduce((o,k)=>o[k]||=( {}),window),get_route:()=>['Form'],router:{on(){}},request:{},flags:{},model:{no_value_type:[]}};
   const fields=['first','second','scan'].map((id,i)=>({df:{fieldname:i===2?'scan_barcode':id,reqd:i<2},$input:$('#'+id)}));
   fields.forEach(field=>field.$input.val('value'));
   window.cur_frm={doctype:'Purchase Invoice',wrapper:document.querySelector('main'),fields,fields_dict:Object.fromEntries(fields.map(field=>[field.df.fieldname,field]))};
  });
  await page.addScriptTag({path:path.resolve(__dirname,'../public/js/retail_keyboard.js')});
  assert.equal(await page.evaluate(()=>$('.datepicker:visible').length),1);
  await page.focus('#first');await page.keyboard.press('Enter');
  await page.waitForFunction(()=>document.activeElement.id==='second');
  await page.keyboard.press('Enter');await page.waitForFunction(()=>document.activeElement.id==='scan');
  await page.focus('#first');await page.keyboard.press('Shift+Enter');await page.waitForFunction(()=>document.activeElement.id==='scan');
  await page.evaluate(()=>$('.datepicker').addClass('active'));
  await page.focus('#first');await page.keyboard.press('Enter');await page.waitForTimeout(900);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'first');
  assert.deepEqual(errors,[]);
 }finally{await browser.close();}
});
test('focus reveal clears nested and overlapping sticky headers and respects later manual scrolling',async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1000,height:700}});
  await page.setContent(`<style>
   body{margin:0} .sticky-top{position:sticky;top:0;height:48px;background:white;z-index:5}
   .navbar{position:relative;height:48px}.page-head{position:sticky;top:24px;height:60px;background:white;z-index:4}
   .form-tabs-list{position:sticky;top:84px;height:43px;background:white;z-index:3}
   input{height:30px} main{min-height:3200px}
   </style><div class="sticky-top"><nav class="navbar">Navigation</nav></div><main>
   <div class="page-head">Toolbar</div><div class="form-tabs-list">Tabs</div>
   <div style="height:200px"></div><input id="scan"><div style="height:1600px"></div><input id="last"></main>`);
  await page.addScriptTag({path:path.resolve(__dirname,'../../../frappe/frappe/public/js/lib/jquery/jquery.min.js')});
  await page.evaluate(()=>{
   window.__=s=>s;window.frappe={provide:p=>p.split('.').reduce((o,k)=>o[k]||={},window),get_route:()=>['Form'],router:{on(){}},request:{},flags:{},model:{no_value_type:[]}};
   const fields=['scan','last'].map(id=>({df:{fieldname:id==='scan'?'scan_barcode':id},$input:$('#'+id)}));
   window.cur_frm={doctype:'Purchase Receipt',wrapper:document.querySelector('main'),fields,fields_dict:Object.fromEntries(fields.map(f=>[f.df.fieldname,f]))};
  });
  await page.addScriptTag({path:path.resolve(__dirname,'../public/js/retail_keyboard.js')});
  await page.focus('#last');await page.keyboard.press('Shift+Enter');
  await page.waitForFunction(()=>document.activeElement.id==='scan');
  const bounds=await page.locator('#scan').boundingBox();
  assert.ok(bounds.y>=163,`Focused field must clear full header stack, got ${bounds.y}`);
  assert.ok(bounds.y+bounds.height<=700);
  await page.evaluate(()=>window.scrollTo({top:1200,behavior:'instant'}));
  await page.waitForTimeout(150);
  assert.equal(await page.evaluate(()=>window.scrollY),1200,'Do not undo manual scrolling');
 }finally{await browser.close();}
});
test('real layout arrows stay on their axis and Enter toggles a checkbox in place',async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage();
  await page.setContent('<main style="display:grid;grid-template-columns:220px 220px;gap:40px"><input id="a"><input id="b" type="checkbox"><input id="c"><input id="d"></main>');
  await page.addScriptTag({path:path.resolve(__dirname,'../../../frappe/frappe/public/js/lib/jquery/jquery.min.js')});
  await page.evaluate(()=>{
   window.__=s=>s;window.frappe={provide:p=>p.split('.').reduce((o,k)=>o[k]||={},window),get_route:()=>['Form'],router:{on(){}},request:{},flags:{},model:{no_value_type:[]}};
   const fields=['a','b','c','d'].map(id=>({df:{fieldname:id,fieldtype:id==='b'?'Check':'Data'},$input:$('#'+id)}));
   window.cur_frm={doctype:'Purchase Invoice',doc:{b:0},wrapper:document.querySelector('main'),fields,fields_dict:Object.fromEntries(fields.map(f=>[f.df.fieldname,f]))};
   $('#b').on('change',function(){cur_frm.doc.b=Number(this.checked);});
  });
  await page.addScriptTag({path:path.resolve(__dirname,'../public/js/retail_keyboard.js')});
  await page.focus('#a');await page.keyboard.press('ArrowRight');await page.waitForFunction(()=>document.activeElement.id==='b');
  await page.keyboard.press('Enter');assert.equal(await page.isChecked('#b'),true);assert.equal(await page.evaluate(()=>cur_frm.doc.b),1);
  await page.keyboard.press('Enter');assert.equal(await page.isChecked('#b'),false);assert.equal(await page.evaluate(()=>cur_frm.doc.b),0);
  assert.equal(await page.evaluate(()=>document.activeElement.id),'b');
  await page.keyboard.press('ArrowDown');await page.waitForFunction(()=>document.activeElement.id==='d');
  await page.keyboard.press('ArrowLeft');await page.waitForFunction(()=>document.activeElement.id==='c');
  await page.keyboard.press('ArrowUp');await page.waitForFunction(()=>document.activeElement.id==='a');
  await page.keyboard.press('ArrowLeft');assert.equal(await page.evaluate(()=>document.activeElement.id),'a');
 }finally{await browser.close();}
});
