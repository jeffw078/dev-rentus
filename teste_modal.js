// Teste do modal
const modal = document.getElementById("modalIdentificar");
console.log("Modal encontrado:", modal);
console.log("Classes do modal:", modal?.classList);

// Tentar abrir
if (modal) {
    modal.classList.add("active");
    console.log("Modal aberto! Classes:", modal.classList);
}
