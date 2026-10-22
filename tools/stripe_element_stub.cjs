// Browser regression double only. Never loaded by storefront templates.
module.exports = `
window.Stripe = key => ({initCheckoutElementsSdk(options) {
  if (!key.startsWith('pk_test_')) throw new Error('Expected publishable test key');
  if(options.elementsOptions.savedPaymentMethod.enableSave !== 'never') throw new Error('Unexpected card saving');
  let declined = false;
  const session = {total:{total:{amount:'£10.50'}}, currency:'gbp'};
  const element = () => {
    let root;
    return {on(){}, mount(node){root=node;node.dataset.testStripeMounted='true';},destroy(){if(root)root.replaceChildren();}};
  };
  return {on(){}, createPaymentElement:element, createExpressCheckoutElement:element,
    loadActions:async()=>({type:'success',actions:{getSession:()=>session,
      confirm:async()=>{if(!declined){declined=true;return {type:'error',error:{message:'Test decline: try again.'}};}return {type:'success',session};}
    }})};
}});
`;
