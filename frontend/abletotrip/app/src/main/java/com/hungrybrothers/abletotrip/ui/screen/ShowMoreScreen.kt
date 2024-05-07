package com.hungrybrothers.abletotrip.ui.screen

import android.util.Log
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.navigation.NavController
import coil.compose.rememberAsyncImagePainter
import com.hungrybrothers.abletotrip.ui.components.HeaderBar
import com.hungrybrothers.abletotrip.ui.datatype.Catalog2Attraction
import com.hungrybrothers.abletotrip.ui.navigation.NavRoute
import com.hungrybrothers.abletotrip.ui.network.ShowMoreInfoRepository
import com.hungrybrothers.abletotrip.ui.viewmodel.ShowMoreViewModel

// 기본화면 구성
@Composable
fun ShowMoreScreen(
    navController: NavController,
    category: String, // 사용되지 않는 매개변수
) {
    val showMoreViewModel: ShowMoreViewModel =
        remember {
            val repository = ShowMoreInfoRepository()
            ShowMoreViewModel(repository)
        }
    Log.d("ShowMoreScreen", "받은 카테고리: $category")
    // ShowMoreData에 category 전달
    LaunchedEffect(Unit) {
        showMoreViewModel.ShowMoreData("37.5665", "126.9780", category, 1)
    }

    Column {
        HeaderBar(navController, true)
        DisplayMoreAttractionsScreen(showMoreViewModel, navController)
    }
}

@Composable
fun DisplayMoreAttractionsScreen(
    viewModel: ShowMoreViewModel,
    navController: NavController,
) {
    val attractionsData by viewModel.showmoreData.collectAsState(null)

    if (attractionsData != null) {
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(vertical = 8.dp),
        ) {
            items(attractionsData!!.attractions) { attraction ->
                Log.d("Catalog", "로드 완료$attraction")
                MoreAttractionItem(attraction, navController)
            }
        }
    } else {
        // 데이터가 없을 때 메시지 표시
        Box(
            modifier = Modifier.fillMaxSize(),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = "해당 카테고리의 데이터가 없습니다.",
                style = MaterialTheme.typography.bodyLarge,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}


// 카탈로그 선택시 화면의 카드
@Composable
fun MoreAttractionItem(
    attraction: Catalog2Attraction,
    navController: NavController,
) {
    Card(
        modifier =
            Modifier
                .fillMaxWidth()
                .padding(vertical = 8.dp, horizontal = 16.dp)
                .clickable(onClick = { navController.navigate("${NavRoute.DETAIL.routeName}/${attraction.id}") }),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
    ) {
        Row(
            modifier =
                Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Image(
                painter = rememberAsyncImagePainter(model = attraction.image_url),
                contentDescription = "Attraction Image",
                modifier =
                    Modifier
                        .size(80.dp)
                        .clip(RoundedCornerShape(8.dp)),
            )
            Spacer(modifier = Modifier.width(16.dp))
            Column(
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    text = attraction.attraction_name,
                    style = MaterialTheme.typography.titleMedium,
                )
                Text(
                    text = "${attraction.si}, ${attraction.gu}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                )
                Text(
                    text = "거리: ${attraction.distance}m",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
        }
    }
}
