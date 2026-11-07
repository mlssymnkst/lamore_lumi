(() => {
  const token = window.location.pathname.split("/").pop();
  const $ = (id) => document.getElementById(id);
  const ratingLabels = ["", "Não gostei", "Pode melhorar", "Regular", "Gostei", "Amei!"];
  let order = null;
  let rating = 0;

  const showError = (message) => {
    $("loading").hidden = true;
    $("rating-step").hidden = true;
    $("details-step").hidden = true;
    $("error").textContent = message;
    $("error").hidden = false;
  };

  const setRating = (value) => {
    rating = value;
    document.querySelectorAll("#stars button").forEach((button) => {
      const active = Number(button.dataset.rating) <= rating;
      button.classList.toggle("active", active);
      button.setAttribute("aria-checked", String(Number(button.dataset.rating) === rating));
    });
    $("rating-hint").textContent = ratingLabels[rating];
    $("continue-rating").disabled = false;
  };

  const validarEstado = () => {
    if ($("customer-state").value) return true;
    $("state-error").textContent = "Selecione o estado onde o pedido foi entregue.";
    $("customer-state").focus();
    return false;
  };

  const updateCount = (field, counter) => {
    $(counter).textContent = String($(field).value.length);
  };

  const openDetails = () => {
    if (!validarEstado()) return;
    $("rating-step").hidden = true;
    $("details-step").hidden = false;
    $("selected-stars").textContent = "★".repeat(rating) + "☆".repeat(5 - rating);
    $("selected-rating").textContent = `${rating} ${rating === 1 ? "estrela" : "estrelas"}`;
    $("issues").hidden = rating === 5;
    $("photo-section").hidden = rating === 5;
    $("recommendation-section").hidden = rating === 5;
    $("comment-label").innerHTML = rating < 5
      ? 'COMENTÁRIO <span class="required">*</span>'
      : "RECOMENDARIA A EMPRESA? (OPCIONAL)";
    $("comment").placeholder = rating < 5
      ? "Descreva o que aconteceu com seu pedido..."
      : "Conte o que você mais gostou...";
    $("comment").classList.toggle("required", rating < 5);
    $("comment-help").textContent = rating < 5 ? "Obrigatório para notas abaixo de 5." : "";
    $("comment").required = rating < 5;
    $("comment-error").textContent = rating < 5
      ? "Campo obrigatório para notas abaixo de 5."
      : "";
    $("photo").required = rating < 5;
    if (rating === 5) {
      document.querySelectorAll('input[name="problemas"]').forEach((input) => { input.checked = false; });
      document.querySelector('select[name="quantidade_correta"]').value = "";
      $("recommendation").value = "";
      $("photo").value = "";
      updateCount("recommendation", "recommendation-count");
      $("photo-error").textContent = "";
    }
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  document.querySelectorAll("#stars button").forEach((button) => {
    button.addEventListener("click", () => setRating(Number(button.dataset.rating)));
  });
  $("continue-rating").addEventListener("click", openDetails);
  $("change-rating").addEventListener("click", () => {
    $("details-step").hidden = true;
    $("rating-step").hidden = false;
  });
  $("comment").addEventListener("input", () => updateCount("comment", "comment-count"));
  $("recommendation").addEventListener("input", () => updateCount("recommendation", "recommendation-count"));
  $("photo").addEventListener("change", () => {
    $("photo-error").textContent = "";
    if ($("photo").files[0]) {
      $("photo-error").textContent = $("photo").files[0].name;
    }
  });
  $("customer-state").addEventListener("change", () => {
    $("state-error").textContent = "";
  });

  $("review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    $("form-error").textContent = "";
    if (!$("customer-state").value) {
      $("details-step").hidden = true;
      $("rating-step").hidden = false;
      validarEstado();
      $("submit-review").disabled = false;
      return;
    }
    $("submit-review").disabled = true;
    const data = new FormData(event.currentTarget);
    data.set("nota", String(rating));
    data.set("uf", $("customer-state").value);
    if (rating === 5) data.delete("foto");
    try {
      const response = await fetch(`/api/avaliacoes/convites/${encodeURIComponent(token)}/avaliar`, {
        method: "POST",
        body: data,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.erro || "Não foi possível enviar sua avaliação.");
      $("customer-state").disabled = true;
      $("details-step").hidden = true;
      $("success-order").textContent = `Pedido #${order.numeroPedido}`;
      $("success-step").hidden = false;
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      $("form-error").textContent = error.message || "Falha de comunicação. Tente novamente.";
      $("submit-review").disabled = false;
    }
  });

  fetch(`/api/avaliacoes/convites/${encodeURIComponent(token)}`)
    .then(async (response) => {
      const result = await response.json();
      if (!response.ok) throw new Error(result.erro || "Este link de avaliação não está disponível.");
      return result;
    })
    .then((result) => {
      order = result;
      $("order-number").textContent = `#${result.numeroPedido}`;
      $("product-name").textContent = result.produto;
      $("customer-name").textContent = `Pedido de ${result.cliente}`;
      const estado = String(result.uf || "").trim().toUpperCase();
      if ([...$("customer-state").options].some((option) => option.value === estado)) {
        $("customer-state").value = estado;
      }
        $("loading").hidden = true;
      $("rating-step").hidden = false;
    })
    .catch((error) => showError(error.message || "Não foi possível carregar o pedido."));
})();
